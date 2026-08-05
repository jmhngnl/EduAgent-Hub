from __future__ import annotations

import hashlib
import math
import re

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Settings
from app.schemas import IntentResult


class DeterministicEmbeddings(Embeddings):
    """Offline deterministic embeddings for local demos and CI.

    This is not semantically strong. It keeps the complete ingestion and
    pgvector pipeline runnable without sending data to an external provider.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


class ModelFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def embeddings(self) -> Embeddings:
        if self.settings.mock_embeddings:
            return DeterministicEmbeddings(self.settings.embedding_dimension)

        if not self.settings.embedding_api_key:
            raise RuntimeError(
                "EMBEDDING_API_KEY is required when MOCK_EMBEDDINGS=false"
            )

        if self.settings.embedding_base_url:
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.embedding_api_key,
                base_url=self.settings.embedding_base_url,
                max_retries=self.settings.llm_max_retries,
                request_timeout=self.settings.llm_timeout_seconds,
            )

        return OpenAIEmbeddings(
            model=self.settings.embedding_model,
            api_key=self.settings.embedding_api_key,
            max_retries=self.settings.llm_max_retries,
            request_timeout=self.settings.llm_timeout_seconds,
        )

    def _resolved_chat_provider(self) -> str:
        configured = self.settings.llm_provider.strip().lower()
        if configured and configured != "auto":
            return configured
        if "deepseek" in self.settings.llm_base_url.lower():
            return "deepseek"
        return "openai-compatible"

    def chat_model(self) -> BaseChatModel:
        if self.settings.mock_llm:
            raise RuntimeError("Chat model is unavailable in MOCK_LLM mode")

        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required when MOCK_LLM=false")

        if self._resolved_chat_provider() == "deepseek":
            thinking_type = (
                "enabled" if self.settings.llm_thinking_enabled else "disabled"
            )
            return ChatDeepSeek(
                model=self.settings.llm_model,
                api_key=self.settings.llm_api_key,
                api_base=self.settings.llm_base_url,
                timeout=self.settings.llm_timeout_seconds,
                max_retries=self.settings.llm_max_retries,
                temperature=0.1,
                extra_body={"thinking": {"type": thinking_type}},
            )

        return ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=self.settings.llm_max_retries,
            temperature=0.1,
        )

    async def classify_intent(self, text: str) -> IntentResult:
        if self.settings.mock_llm:
            lowered = text.lower()
            if re.search(r"\d+\s*[\+\-\*/]\s*\d+", lowered):
                return IntentResult(
                    intent="calculation",
                    confidence=0.92,
                    requires_tool=True,
                    suggested_tool="safe_calculator",
                    reason="检测到明确的算术表达式。",
                )
            if any(word in lowered for word in ("总结", "摘要", "概括", "summarize")):
                return IntentResult(
                    intent="document_summary",
                    confidence=0.86,
                    requires_tool=True,
                    suggested_tool="search_knowledge",
                    reason="请求对文档内容进行总结。",
                )
            if any(word in lowered for word in ("计划", "步骤", "安排", "workflow")):
                return IntentResult(
                    intent="task_planning",
                    confidence=0.80,
                    requires_tool=False,
                    suggested_tool=None,
                    reason="请求拆解任务或生成执行计划。",
                )
            return IntentResult(
                intent="knowledge_question",
                confidence=0.78,
                requires_tool=True,
                suggested_tool="search_knowledge",
                reason="默认作为知识库问答处理。",
            )

        model = self.chat_model().with_structured_output(IntentResult)
        result = await model.ainvoke(
            [
                (
                    "system",
                    "你是意图分类器。严格按照给定 Schema 返回，不回答用户问题本身。",
                ),
                ("human", text),
            ]
        )
        if not isinstance(result, IntentResult):
            return IntentResult.model_validate(result)
        return result
