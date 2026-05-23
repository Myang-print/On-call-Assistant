import logging

from app.documents import DocumentStore, load_documents_from_data_dir
from app.settings import DATA_DIR
from app.models import Document


logger = logging.getLogger(__name__)


def test_load_documents_uses_html_filename_stem_as_doc_id() -> None:
    documents = load_documents_from_data_dir(DATA_DIR)

    logger.info("loaded_doc_ids=%s", [document.doc_id for document in documents])
    assert [document.doc_id for document in documents] == [
        "sop-001",
        "sop-002",
        "sop-003",
        "sop-004",
        "sop-005",
        "sop-006",
        "sop-007",
        "sop-008",
        "sop-009",
        "sop-010",
    ]
    assert documents[0].title == "后端服务 On-Call SOP"
    assert documents[1].title == "数据库DBA On-Call SOP"


def test_all_loaded_html_passes_through_parser() -> None:
    documents = load_documents_from_data_dir(DATA_DIR)
    documents_by_id = {document.doc_id: document for document in documents}

    logger.info("sop_002_cleaned_text=%s", documents_by_id["sop-002"].cleaned_text)
    assert len(documents) == 10
    assert all(isinstance(document, Document) for document in documents)
    assert "主从延迟" in documents_by_id["sop-002"].cleaned_text
    assert "replicationLag" not in documents_by_id["sop-002"].cleaned_text
    assert "style.backgroundColor" not in documents_by_id["sop-002"].cleaned_text
    assert "调度系统显示大量离线任务失败" in documents_by_id["sop-006"].cleaned_text
    assert "banner.style.cssText" not in documents_by_id["sop-006"].cleaned_text


def test_document_store_keeps_loaded_documents_in_memory_copy() -> None:
    source_documents = [
        Document(
            doc_id="sop-005",
            raw_html="<html><head><title>Security SOP</title></head><body><p>入侵检测。</p></body></html>",
            title="Security SOP",
            cleaned_text="Security SOP 入侵检测。",
        )
    ]
    store = DocumentStore(source_documents)
    source_documents.clear()

    document = store.get("sop-005")
    logger.info("stored_document=%s", document)
    assert document == Document(
        doc_id="sop-005",
        raw_html="<html><head><title>Security SOP</title></head><body><p>入侵检测。</p></body></html>",
        title="Security SOP",
        cleaned_text="Security SOP 入侵检测。",
    )


def test_document_store_returns_copied_containers() -> None:
    store = DocumentStore.from_data_dir(DATA_DIR)

    first_snapshot = store.all()
    first_snapshot.clear()

    logger.info("first_snapshot_len=%s store_len=%s", len(first_snapshot), len(store.all()))
    assert first_snapshot == []
    assert len(store.all()) == 10
    assert store.get("missing") is None
