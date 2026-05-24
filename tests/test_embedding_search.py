import logging

from fastapi.testclient import TestClient

from app.embedding_search import (
    BGE_M3_MODEL_NAME,
    EMBEDDING_ENABLED_ENV,
    embedding_search_with_fallback,
    is_embedding_enabled,
    rank_documents_by_embeddings,
)
from app.main import app
from app.models import Document


logger = logging.getLogger(__name__)


class FakeEmbeddingModel:
    def encode(self, texts: list[str]) -> list[list[float]]:
        mapping = {
            "query": [1.0, 0.0],
            "Backend SOP\nbackend service": [1.0, 0.0],
            "Security SOP\nsecurity incident": [0.25, 1.0],
        }
        return [mapping[text] for text in texts]


class FailingEmbeddingModel:
    def encode(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding unavailable")


def test_embedding_model_name_prefers_bge_m3() -> None:
    logger.info("embedding_model_name=%s", BGE_M3_MODEL_NAME)
    assert BGE_M3_MODEL_NAME == "BAAI/bge-m3"


def test_embedding_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv(EMBEDDING_ENABLED_ENV, raising=False)

    logger.info("embedding_enabled_default=%s", is_embedding_enabled())
    assert is_embedding_enabled() is False


def test_rank_documents_by_embeddings_orders_by_similarity_then_id() -> None:
    documents = [
        Document("sop-005", "", "Security SOP", "security incident"),
        Document("sop-001", "", "Backend SOP", "backend service"),
    ]

    results = rank_documents_by_embeddings(documents, "query", FakeEmbeddingModel())

    logger.info("embedding_results=%s", results)
    assert [result["id"] for result in results] == ["sop-001", "sop-005"]
    assert results[0]["score"] > results[1]["score"]


def test_embedding_search_falls_back_to_semantic_search_when_embedding_fails() -> None:
    documents = [
        Document("sop-005", "", "安全团队 On-Call SOP", "安全 攻击 入侵 DDoS"),
        Document("sop-001", "", "后端服务 On-Call SOP", "后端 服务 超时"),
    ]
    dictionary = {"黑客攻击": ["安全", "攻击", "入侵", "DDoS"]}

    results = embedding_search_with_fallback(
        documents,
        "黑客攻击",
        dictionary,
        model=FailingEmbeddingModel(),
    )

    logger.info("fallback_results=%s", results)
    assert results[0]["id"] == "sop-005"


def test_embedding_search_uses_semantic_search_when_default_embedding_disabled(monkeypatch) -> None:
    monkeypatch.delenv(EMBEDDING_ENABLED_ENV, raising=False)
    documents = [
        Document("sop-005", "", "安全团队 On-Call SOP", "安全 攻击 入侵 DDoS"),
        Document("sop-001", "", "后端服务 On-Call SOP", "后端 服务 超时"),
    ]
    dictionary = {"黑客攻击": ["安全", "攻击", "入侵", "DDoS"]}

    results = embedding_search_with_fallback(documents, "黑客攻击", dictionary)

    logger.info("embedding_disabled_semantic_results=%s", results)
    assert results[0]["id"] == "sop-005"


def test_v2_search_route_remains_available_without_optional_embedding_dependency() -> None:
    client = TestClient(app)

    response = client.get("/v2/search", params={"q": "黑客攻击"})

    logger.info("v2_embedding_fallback_body=%s", response.json())
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "sop-005"
