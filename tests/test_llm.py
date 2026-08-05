import pytest

from app.config import Settings
from app.llm import DeterministicEmbeddings, ModelFactory


def test_real_chat_can_use_mock_embeddings() -> None:
    settings = Settings(
        mock_llm=False,
        llm_api_key="provider-key",
        llm_base_url="https://api.example.com",
        llm_model="chat-model",
        mock_embeddings=True,
        embedding_dimension=128,
    )

    embeddings = ModelFactory(settings).embeddings()

    assert isinstance(embeddings, DeterministicEmbeddings)
    assert len(embeddings.embed_query("GPU 申请")) == 128


def test_remote_embeddings_require_dedicated_key() -> None:
    settings = Settings(mock_embeddings=False, embedding_api_key="")

    with pytest.raises(RuntimeError, match="EMBEDDING_API_KEY"):
        ModelFactory(settings).embeddings()
