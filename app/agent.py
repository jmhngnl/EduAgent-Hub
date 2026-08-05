from __future__ import annotations

import ast
import asyncio
import json
import logging
import operator
import re
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from redis.asyncio import Redis

from app.config import Settings
from app.llm import ModelFactory
from app.prompts import build_agent_system_prompt
from app.rag import KnowledgeStore, RetrievedChunk
from app.schemas import ChatResponse, Citation

logger = logging.getLogger(__name__)


class UnsafeExpressionError(ValueError):
    pass


_BINARY_OPERATORS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str) -> float:
    """Evaluate arithmetic without eval(), names, calls, attributes or indexing."""

    if len(expression) > 200:
        raise UnsafeExpressionError("Expression is too long")

    parsed = ast.parse(expression, mode="eval")

    def visit(node: ast.AST, depth: int = 0) -> float:
        if depth > 12:
            raise UnsafeExpressionError("Expression is too deeply nested")

        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)

        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            if abs(node.value) > 1e50:
                raise UnsafeExpressionError("Numeric literal is too large")
            return float(node.value)

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = visit(node.left, depth + 1)
            right = visit(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise UnsafeExpressionError("Exponent is too large")
            return float(_BINARY_OPERATORS[type(node.op)](left, right))

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return float(_UNARY_OPERATORS[type(node.op)](visit(node.operand, depth + 1)))

        raise UnsafeExpressionError(f"Unsupported syntax: {type(node).__name__}")

    result = visit(parsed)
    if abs(result) > 1e100:
        raise UnsafeExpressionError("Result magnitude is too large")
    return result


_PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"developer\s+message",
    r"忽略.{0,8}(之前|以上).{0,8}(指令|提示)",
    r"(泄露|输出|展示).{0,8}(系统提示词|system prompt)",
)


def detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in _PROMPT_INJECTION_PATTERNS)


def extract_arithmetic_expression(text: str) -> str | None:
    candidates = re.findall(r"[0-9eE\.\+\-\*/%()\s]+", text)
    candidates = [
        candidate.strip()
        for candidate in candidates
        if any(operator_token in candidate for operator_token in ("+", "-", "*", "/", "%"))
        and any(char.isdigit() for char in candidate)
    ]
    return max(candidates, key=len) if candidates else None


class RedisConversationStore:
    def __init__(self, redis: Redis, max_messages: int = 16) -> None:
        self.redis = redis
        self.max_messages = max_messages

    @staticmethod
    def _key(session_id: str) -> str:
        return f"eduagent:conversation:{session_id}"

    async def load(self, session_id: str) -> list[dict[str, str]]:
        raw = await self.redis.get(self._key(session_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [
            item
            for item in data
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ][-self.max_messages :]

    async def append(self, session_id: str, role: str, content: str) -> None:
        history = await self.load(session_id)
        history.append({"role": role, "content": content})
        history = history[-self.max_messages :]
        await self.redis.set(
            self._key(session_id),
            json.dumps(history, ensure_ascii=False),
            ex=60 * 60 * 24 * 7,
        )

    async def ping(self) -> bool:
        return bool(await self.redis.ping())


class InMemoryConversationStore:
    def __init__(self, max_messages: int = 16) -> None:
        self.max_messages = max_messages
        self.data: dict[str, list[dict[str, str]]] = {}

    async def load(self, session_id: str) -> list[dict[str, str]]:
        return list(self.data.get(session_id, []))[-self.max_messages :]

    async def append(self, session_id: str, role: str, content: str) -> None:
        self.data.setdefault(session_id, []).append({"role": role, "content": content})
        self.data[session_id] = self.data[session_id][-self.max_messages :]

    async def ping(self) -> bool:
        return True


ConversationStore = RedisConversationStore | InMemoryConversationStore


def _citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(
            document_id=chunk.document_id,
            source=chunk.source,
            chunk_id=chunk.id,
            score=chunk.score,
        )
        for chunk in chunks
    ]


def _context_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "当前知识库没有检索到足够上下文。"

    sections: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        sections.append(
            f"[来源{index}] source={chunk.source}; document_id={chunk.document_id}\n"
            f"{chunk.content}"
        )
    return "\n\n".join(sections)


class AgentService:
    """LangGraph tool-calling agent with tenant-scoped RAG context."""

    def __init__(
        self,
        *,
        settings: Settings,
        knowledge: KnowledgeStore,
        conversations: ConversationStore,
    ) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self.conversations = conversations
        self.model_factory = ModelFactory(settings)

    def _build_graph(self, *, workspace_id: str, context: str):
        model = self.model_factory.chat_model()

        @tool
        async def search_knowledge(query: str) -> str:
            """Search the current workspace knowledge base for grounded evidence."""
            chunks = await self.knowledge.search(
                workspace_id=workspace_id,
                query=query,
                top_k=self.settings.retrieval_top_k,
            )
            payload = [
                {
                    "source": item.source,
                    "document_id": item.document_id,
                    "content": item.content,
                    "score": item.score,
                }
                for item in chunks
            ]
            return json.dumps(payload, ensure_ascii=False)

        @tool
        def safe_calculator(expression: str) -> str:
            """Calculate a basic arithmetic expression without executing code."""
            try:
                return str(safe_calculate(expression))
            except (SyntaxError, ZeroDivisionError, UnsafeExpressionError) as exc:
                return f"calculation_error: {exc}"

        tools = [search_knowledge, safe_calculator]
        bound_model = model.bind_tools(tools)
        system_message = SystemMessage(
            content=build_agent_system_prompt(context=context, workspace_id=workspace_id)
        )

        async def assistant(state: MessagesState) -> dict[str, list[AIMessage]]:
            response = await bound_model.ainvoke([system_message, *state["messages"]])
            return {"messages": [response]}

        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("assistant", assistant)
        graph_builder.add_node("tools", ToolNode(tools))
        graph_builder.set_entry_point("assistant")
        graph_builder.add_conditional_edges(
            "assistant",
            tools_condition,
            {"tools": "tools", END: END},
        )
        graph_builder.add_edge("tools", "assistant")
        return graph_builder.compile()

    async def _history_messages(self, session_id: str) -> list[HumanMessage | AIMessage]:
        history = await self.conversations.load(session_id)
        messages: list[HumanMessage | AIMessage] = []
        for item in history:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            else:
                messages.append(AIMessage(content=item["content"]))
        return messages

    async def _prefetch(
        self,
        *,
        workspace_id: str,
        message: str,
    ) -> list[RetrievedChunk]:
        return await self.knowledge.search(
            workspace_id=workspace_id,
            query=message,
            top_k=self.settings.retrieval_top_k,
        )

    async def chat(
        self,
        *,
        message: str,
        session_id: str,
        workspace_id: str,
    ) -> ChatResponse:
        if len(message) > self.settings.max_user_input_chars:
            raise ValueError("User input exceeds the configured maximum length")

        guarded = detect_prompt_injection(message)
        if guarded:
            answer = (
                "检测到可能绕过系统边界或索取内部提示词的请求。"
                "我不会执行该部分指令，但可以继续回答正常的业务问题。"
            )
            await self.conversations.append(session_id, "user", message)
            await self.conversations.append(session_id, "assistant", answer)
            return ChatResponse(
                answer=answer,
                session_id=session_id,
                guarded=True,
            )

        chunks = await self._prefetch(
            workspace_id=workspace_id,
            message=message,
        )
        citations = _citations(chunks)
        context = _context_block(chunks)

        if self.settings.mock_llm:
            expression = extract_arithmetic_expression(message)
            if expression is not None:
                try:
                    answer = f"计算结果：{safe_calculate(expression):g}"
                except (SyntaxError, ZeroDivisionError, UnsafeExpressionError):
                    answer = "检测到算术意图，但表达式无法安全计算。"
                tool_calls = ["safe_calculator"]
            elif chunks:
                summaries = "\n\n".join(
                    f"[来源{index}] {chunk.content[:360]}"
                    for index, chunk in enumerate(chunks[:3], start=1)
                )
                answer = (
                    "当前运行在 MOCK_LLM 模式。根据知识库检索结果，可参考：\n\n"
                    f"{summaries}\n\n"
                    "接入真实 OpenAI-compatible 模型后，LangGraph 会进一步完成"
                    "工具选择、综合推理和自然语言生成。"
                )
                tool_calls = ["search_knowledge"]
            else:
                answer = (
                    "当前运行在 MOCK_LLM 模式，且知识库没有检索到相关内容。"
                    "请先上传文档，或配置真实模型后再试。"
                )
                tool_calls = ["search_knowledge"]
        else:
            graph = self._build_graph(workspace_id=workspace_id, context=context)
            messages = [
                *await self._history_messages(session_id),
                HumanMessage(content=message),
            ]
            result = await graph.ainvoke(
                {"messages": messages},
                config={"recursion_limit": 8},
            )
            final_message = next(
                (
                    item
                    for item in reversed(result["messages"])
                    if isinstance(item, AIMessage) and item.content
                ),
                None,
            )
            answer = (
                str(final_message.content)
                if final_message is not None
                else "Agent 未生成有效回答，请稍后重试。"
            )
            tool_calls = [
                call.get("name", "unknown")
                for item in result["messages"]
                if isinstance(item, AIMessage)
                for call in getattr(item, "tool_calls", [])
            ]

        await self.conversations.append(session_id, "user", message)
        await self.conversations.append(session_id, "assistant", answer)

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            citations=citations,
            tool_calls=tool_calls,
        )

    async def stream(
        self,
        *,
        message: str,
        session_id: str,
        workspace_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream model events. Mock mode streams the deterministic response."""

        if self.settings.mock_llm or detect_prompt_injection(message):
            result = await self.chat(
                message=message,
                session_id=session_id,
                workspace_id=workspace_id,
            )
            for start in range(0, len(result.answer), 40):
                yield {"type": "token", "data": result.answer[start : start + 40]}
                await asyncio.sleep(0)
            yield {
                "type": "done",
                "data": {
                    "session_id": session_id,
                    "citations": [
                        citation.model_dump() for citation in result.citations
                    ],
                    "tool_calls": result.tool_calls,
                    "guarded": result.guarded,
                },
            }
            return

        chunks = await self._prefetch(
            workspace_id=workspace_id,
            message=message,
        )
        context = _context_block(chunks)
        graph = self._build_graph(workspace_id=workspace_id, context=context)
        messages = [
            *await self._history_messages(session_id),
            HumanMessage(content=message),
        ]

        answer_parts: list[str] = []
        tool_calls: list[str] = []

        try:
            async for event in graph.astream_events(
                {"messages": messages},
                config={"recursion_limit": 8},
                version="v2",
            ):
                event_name = event.get("event")
                data = event.get("data", {})

                if event_name == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    content = getattr(chunk, "content", "")
                    if isinstance(content, str) and content:
                        answer_parts.append(content)
                        yield {"type": "token", "data": content}

                if event_name == "on_tool_start":
                    name = str(event.get("name", "unknown"))
                    tool_calls.append(name)
                    yield {"type": "tool_start", "data": {"name": name}}

                if event_name == "on_tool_end":
                    yield {
                        "type": "tool_end",
                        "data": {"name": str(event.get("name", "unknown"))},
                    }
        except Exception:
            logger.exception("Streaming model request failed")
            yield {
                "type": "error",
                "data": {
                    "message": (
                        "模型服务调用失败。请在服务器 .env 中检查 MOCK_LLM、"
                        "LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL；浏览器中的"
                        " X-API-Key 仅用于访问 EduAgent Hub 后端。"
                    )
                },
            }
            return

        answer = "".join(answer_parts).strip() or "Agent 未生成有效回答，请稍后重试。"
        await self.conversations.append(session_id, "user", message)
        await self.conversations.append(session_id, "assistant", answer)

        yield {
            "type": "done",
            "data": {
                "session_id": session_id,
                "citations": [item.model_dump() for item in _citations(chunks)],
                "tool_calls": tool_calls,
                "guarded": False,
            },
        }
