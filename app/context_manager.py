from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import Settings
from app.llm import ModelFactory
from app.rag import RetrievedChunk
from app.schemas import ConversationContext, ConversationContextUpdate, ConversationMessage

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Provider-neutral token estimate for context budgeting, not billing."""
    if not text:
        return 0
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, math.ceil(ascii_chars / 4.0 + non_ascii_chars / 1.5))


def _message_tokens(message: ConversationMessage) -> int:
    return estimate_tokens(message.content) + 4


def _trim_text(text: str, max_tokens: int, *, keep_tail: bool = False) -> str:
    if max_tokens <= 0 or not text:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[-middle:] if keep_tail else text[:middle]
        if estimate_tokens(candidate) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    if low <= 0:
        return ""
    trimmed = text[-low:] if keep_tail else text[:low]
    return ("…" + trimmed) if keep_tail else (trimmed + "…")


@dataclass(slots=True)
class PreparedContext:
    summary: str
    recent_messages: list[HumanMessage | AIMessage]
    rag_context: str
    context_stats: dict[str, Any]
    context_update: ConversationContextUpdate | None


class ContextManager:
    """Build bounded model context from MySQL-backed conversation history + RAG."""

    def __init__(self, settings: Settings, model_factory: ModelFactory) -> None:
        self.settings = settings
        self.model_factory = model_factory

    async def prepare(
        self,
        *,
        conversation_context: ConversationContext,
        current_message: str,
        chunks: list[RetrievedChunk],
    ) -> PreparedContext:
        existing_summary = conversation_context.summary.strip()
        unsummarized = list(conversation_context.messages)

        recent, older = self._select_recent(
            unsummarized,
            self.settings.context_recent_history_tokens,
        )

        stored_summary = existing_summary
        context_update: ConversationContextUpdate | None = None
        if older:
            stored_summary = await self._roll_summary(existing_summary, older)
            context_update = ConversationContextUpdate(
                summary=stored_summary,
                summarized_message_count=(
                    conversation_context.summarized_message_count + len(older)
                ),
            )

        prompt_summary = _trim_text(
            stored_summary,
            self.settings.context_summary_max_tokens,
        )
        rag_context, rag_chunk_count = self._build_rag_context(
            chunks,
            self.settings.context_rag_tokens,
        )

        recent = self._fit_total_budget(
            recent=recent,
            summary=prompt_summary,
            rag_context=rag_context,
            current_message=current_message,
        )

        recent_tokens = sum(_message_tokens(item) for item in recent)
        summary_tokens = estimate_tokens(prompt_summary)
        rag_tokens = estimate_tokens(rag_context)
        current_tokens = estimate_tokens(current_message)
        estimated_input = (
            self.settings.context_system_reserve_tokens
            + summary_tokens
            + recent_tokens
            + rag_tokens
            + current_tokens
        )
        max_prompt_tokens = max(
            1,
            self.settings.context_max_input_tokens
            - self.settings.context_reserved_output_tokens,
        )

        # Current message + system instructions have priority. If necessary,
        # reduce RAG after older conversation turns have already been removed.
        if estimated_input > max_prompt_tokens and rag_context:
            remaining_rag = max(
                0,
                max_prompt_tokens
                - self.settings.context_system_reserve_tokens
                - summary_tokens
                - recent_tokens
                - current_tokens,
            )
            rag_context = _trim_text(rag_context, remaining_rag)
            rag_tokens = estimate_tokens(rag_context)
            estimated_input = (
                self.settings.context_system_reserve_tokens
                + summary_tokens
                + recent_tokens
                + rag_tokens
                + current_tokens
            )

        langchain_messages: list[HumanMessage | AIMessage] = []
        for item in recent:
            if item.role == "user":
                langchain_messages.append(HumanMessage(content=item.content))
            else:
                langchain_messages.append(AIMessage(content=item.content))

        stats: dict[str, Any] = {
            "strategy": "rolling-summary+recent-window+rag-budget",
            "summary_used": bool(prompt_summary),
            "summary_updated": context_update is not None,
            "summarized_message_count": (
                context_update.summarized_message_count
                if context_update is not None
                else conversation_context.summarized_message_count
            ),
            "received_unsummarized_messages": len(unsummarized),
            "recent_message_count": len(recent),
            "recent_message_tokens": recent_tokens,
            "summary_tokens": summary_tokens,
            "rag_chunk_count": rag_chunk_count,
            "rag_tokens": rag_tokens,
            "current_message_tokens": current_tokens,
            "estimated_input_tokens": estimated_input,
            "max_input_tokens": self.settings.context_max_input_tokens,
            "reserved_output_tokens": self.settings.context_reserved_output_tokens,
        }

        return PreparedContext(
            summary=prompt_summary,
            recent_messages=langchain_messages,
            rag_context=rag_context,
            context_stats=stats,
            context_update=context_update,
        )

    def _select_recent(
        self,
        messages: list[ConversationMessage],
        budget: int,
    ) -> tuple[list[ConversationMessage], list[ConversationMessage]]:
        if not messages:
            return [], []
        if budget <= 0:
            return [], messages

        selected_reversed: list[ConversationMessage] = []
        used = 0
        split_index = len(messages)

        for index in range(len(messages) - 1, -1, -1):
            item = messages[index]
            cost = _message_tokens(item)
            if selected_reversed and used + cost > budget:
                break
            if not selected_reversed and cost > budget:
                selected_reversed.append(
                    ConversationMessage(
                        role=item.role,
                        content=_trim_text(
                            item.content,
                            max(1, budget - 4),
                            keep_tail=True,
                        ),
                    )
                )
                split_index = index
                break
            selected_reversed.append(item)
            used += cost
            split_index = index

        return list(reversed(selected_reversed)), messages[:split_index]

    def _fit_total_budget(
        self,
        *,
        recent: list[ConversationMessage],
        summary: str,
        rag_context: str,
        current_message: str,
    ) -> list[ConversationMessage]:
        max_prompt_tokens = max(
            1,
            self.settings.context_max_input_tokens
            - self.settings.context_reserved_output_tokens,
        )
        current = list(recent)
        while current:
            estimated = (
                self.settings.context_system_reserve_tokens
                + estimate_tokens(summary)
                + sum(_message_tokens(item) for item in current)
                + estimate_tokens(rag_context)
                + estimate_tokens(current_message)
            )
            if estimated <= max_prompt_tokens:
                break
            current.pop(0)
        return current

    def _build_rag_context(
        self,
        chunks: list[RetrievedChunk],
        budget: int,
    ) -> tuple[str, int]:
        if not chunks or budget <= 0:
            return "当前知识库没有检索到足够上下文。", 0

        sections: list[str] = []
        used = 0
        used_chunks = 0
        for index, chunk in enumerate(chunks, start=1):
            prefix = (
                f"[来源{index}] source={chunk.source}; "
                f"document_id={chunk.document_id}\n"
            )
            remaining = budget - used - estimate_tokens(prefix)
            if remaining <= 0:
                break
            content = _trim_text(chunk.content, remaining)
            if not content:
                break
            section = prefix + content
            section_tokens = estimate_tokens(section)
            if used + section_tokens > budget:
                break
            sections.append(section)
            used += section_tokens
            used_chunks += 1

        if not sections:
            return "当前知识库没有检索到足够上下文。", 0
        return "\n\n".join(sections), used_chunks

    async def _roll_summary(
        self,
        existing_summary: str,
        older_messages: list[ConversationMessage],
    ) -> str:
        if self.settings.mock_llm:
            return self._fallback_summary(existing_summary, older_messages)

        source = self._summary_source(existing_summary, older_messages)
        system = SystemMessage(
            content=(
                "你是 EduAgent Hub 的会话记忆压缩器。"
                "只根据提供的历史内容生成简洁摘要，不得补充不存在的信息。"
                "优先保留用户稳定事实与偏好、研究主题、已做决定、关键实体、"
                "重要结论和未解决问题；忽略寒暄与重复。"
                "若新信息与旧摘要冲突，以时间更近的信息为准。"
                "输出纯文本摘要，不输出分析过程。"
            )
        )
        try:
            response = await self.model_factory.chat_model().ainvoke(
                [system, HumanMessage(content=source)]
            )
            content = response.content
            if isinstance(content, str) and content.strip():
                return _trim_text(
                    content.strip(),
                    self.settings.context_summary_max_tokens,
                )
        except Exception:
            logger.exception("Conversation summary compression failed; using fallback")
        return self._fallback_summary(existing_summary, older_messages)

    def _summary_source(
        self,
        existing_summary: str,
        messages: list[ConversationMessage],
    ) -> str:
        lines: list[str] = []
        if existing_summary:
            lines.extend(["【已有摘要】", existing_summary])
        lines.append("【本次需要压缩的较早对话】")
        for item in messages:
            label = "用户" if item.role == "user" else "助手"
            lines.append(f"{label}: {item.content}")
        return _trim_text(
            "\n".join(lines),
            self.settings.context_summary_source_tokens,
            keep_tail=True,
        )

    def _fallback_summary(
        self,
        existing_summary: str,
        messages: list[ConversationMessage],
    ) -> str:
        # Keeps tests/MOCK mode independent of an external model.
        parts: list[str] = []
        if existing_summary:
            parts.append("已有摘要：" + _trim_text(existing_summary, 700))
        for item in messages[-10:]:
            label = "用户" if item.role == "user" else "助手"
            parts.append(f"{label}: {_trim_text(item.content.strip(), 220)}")
        return _trim_text(
            "\n".join(parts),
            self.settings.context_summary_max_tokens,
        )
