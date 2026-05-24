import logging
from pathlib import Path

from app.documents import DocumentStore
from app.semantic_search import expand_query, load_domain_dictionary, semantic_search_documents


logger = logging.getLogger(__name__)


DICTIONARY_PATH = Path("data/domain_dictionary.json")


def test_load_domain_dictionary_contains_required_expansions() -> None:
    dictionary = load_domain_dictionary(DICTIONARY_PATH)

    logger.info("dictionary_keys=%s", sorted(dictionary))
    assert "服务器挂了" in dictionary
    assert "黑客攻击" in dictionary
    assert "机器学习模型出问题" in dictionary


def test_expand_query_uses_domain_dictionary_terms() -> None:
    dictionary = load_domain_dictionary(DICTIONARY_PATH)

    expanded_terms = expand_query("服务器挂了", dictionary)

    logger.info("expanded_terms=%s", expanded_terms)
    assert expanded_terms[0] == "服务器挂了"
    assert "后端" in expanded_terms
    assert "基础设施" in expanded_terms
    assert "K8s" in expanded_terms


def test_semantic_search_ranks_backend_and_sre_for_server_down_query() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DICTIONARY_PATH)

    results = semantic_search_documents(documents, "服务器挂了", dictionary)

    logger.info("server_down_results=%s", results[:5])
    assert {result["id"] for result in results[:2]} == {"sop-001", "sop-004"}


def test_semantic_search_ranks_security_for_hacker_attack_query() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DICTIONARY_PATH)

    results = semantic_search_documents(documents, "黑客攻击", dictionary)

    logger.info("security_results=%s", results[:5])
    assert results[0]["id"] == "sop-005"


def test_semantic_search_ranks_ai_for_machine_learning_model_issue_query() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DICTIONARY_PATH)

    results = semantic_search_documents(documents, "机器学习模型出问题", dictionary)

    logger.info("ai_results=%s", results[:5])
    assert results[0]["id"] == "sop-008"


def test_domain_dictionary_expansion_covers_sop_001_to_sop_010() -> None:
    documents = DocumentStore.from_data_dir().all()
    dictionary = load_domain_dictionary(DICTIONARY_PATH)
    coverage_queries = {
        "sop-001": "后端服务异常",
        "sop-002": "数据库主从延迟",
        "sop-003": "页面白屏",
        "sop-004": "K8s集群故障",
        "sop-005": "黑客攻击",
        "sop-006": "ETL任务失败",
        "sop-007": "App崩溃",
        "sop-008": "机器学习模型出问题",
        "sop-009": "自动化测试失败",
        "sop-010": "CDN节点故障",
    }

    uncovered_doc_ids: list[str] = []
    for expected_doc_id, query in coverage_queries.items():
        top5_ids = [
            result["id"]
            for result in semantic_search_documents(documents, query, dictionary)[:5]
        ]
        logger.info("coverage_query=%s top5_ids=%s", query, top5_ids)
        if expected_doc_id not in top5_ids:
            uncovered_doc_ids.append(expected_doc_id)

    assert uncovered_doc_ids == []
