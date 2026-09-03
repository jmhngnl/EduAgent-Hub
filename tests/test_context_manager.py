import pytest

from app.config import Settings
from app.context_manager import ContextManager, estimate_tokens
from app.llm import ModelFactory
from app.schemas import ConversationContext, ConversationMessage


def test_estimate_tokens_is_nonzero_and_cjk_is_conservative() -> None:
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("这是中文上下文管理测试") >= 4


@pytest.mark.asyncio
async def test_context_manager_rolls_old_messages_into_summary() -> None:
    settings = Settings(
        mock_llm=True,
        context_max_input_tokens=300,
        context_reserved_output_tokens=40,
        context_system_reserve_tokens=30,
        context_recent_history_tokens=70,
        context_summary_max_tokens=60,
        context_summary_source_tokens=120,
        context_rag_tokens=50,
    )
    manager = ContextManager(settings, ModelFactory(settings))
    context = ConversationContext(
        summary="用户正在研究 Agent Memory。",
        summarized_message_count=2,
        messages=[
            ConversationMessage(role="user", content="较早问题 " + "A" * 180),
            ConversationMessage(role="assistant", content="较早回答 " + "B" * 180),
            ConversationMessage(role="user", content="最近问题：上下文怎么裁剪？"),
            ConversationMessage(role="assistant", content="最近回答：可以按 token budget。"),
        ],
    )

    prepared = await manager.prepare(
        conversation_context=context,
        current_message="继续解释 rolling summary。",
        chunks=[],
    )

    assert prepared.context_update is not None
    assert prepared.context_update.summarized_message_count > 2
    assert prepared.context_stats["summary_updated"] is True
    assert prepared.context_stats["recent_message_count"] >= 1


@pytest.mark.asyncio
async def test_context_manager_keeps_short_history_without_summary_update() -> None:
    settings = Settings(mock_llm=True)
    manager = ContextManager(settings, ModelFactory(settings))
    context = ConversationContext(
        messages=[
            ConversationMessage(role="user", content="什么是 Flow Matching？"),
            ConversationMessage(role="assistant", content="它是一类连续生成建模方法。"),
        ]
    )

    prepared = await manager.prepare(
        conversation_context=context,
        current_message="它和 diffusion 有什么区别？",
        chunks=[],
    )

    assert prepared.context_update is None
    assert prepared.context_stats["recent_message_count"] == 2
