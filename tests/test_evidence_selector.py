import json
import logging
from pathlib import Path

from app.evidence_selector import select_sop_filenames


logger = logging.getLogger(__name__)
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "data" / "manifest.json"


def _manifest() -> list[dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_oom_query_selects_backend_sop_first() -> None:
    selected = select_sop_filenames("服务 OOM 了怎么办？", _manifest())

    logger.info("oom_selected=%s", selected)
    assert selected[0] == "sop-001.html"


def test_database_replication_lag_selects_dba_sop() -> None:
    selected = select_sop_filenames("数据库主从延迟超过30秒怎么处理？", _manifest())

    logger.info("replication_lag_selected=%s", selected)
    assert selected[0] == "sop-002.html"


def test_intrusion_query_selects_security_sop() -> None:
    selected = select_sop_filenames("怀疑有人入侵了系统", _manifest())

    logger.info("intrusion_selected=%s", selected)
    assert selected[0] == "sop-005.html"


def test_recommendation_quality_query_selects_ai_sop() -> None:
    selected = select_sop_filenames("推荐结果质量下降了", _manifest())

    logger.info("recommendation_quality_selected=%s", selected)
    assert selected[0] == "sop-008.html"


def test_selector_ignores_manifest_entries_without_safe_html_filename() -> None:
    manifest = [
        {"doc_id": "safe", "filename": "safe.html", "title": "安全 SOP", "keywords": ["入侵"]},
        {"doc_id": "unsafe", "filename": "../unsafe.html", "title": "入侵 SOP", "keywords": ["入侵"]},
        {"doc_id": "json", "filename": "manifest.json", "title": "入侵 SOP", "keywords": ["入侵"]},
    ]

    selected = select_sop_filenames("入侵", manifest)

    assert selected == ["safe.html"]
