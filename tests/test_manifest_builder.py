import json
import logging
from uuid import uuid4
from pathlib import Path

from app.manifest_builder import update_manifest


logger = logging.getLogger(__name__)
TMP_ROOT = Path(__file__).resolve().parent / ".tmp_manifest_builder"


def _fresh_data_dir() -> Path:
    data_dir = TMP_ROOT / uuid4().hex / "data"
    data_dir.mkdir(parents=True)
    return data_dir


def test_manifest_builder_updates_manifest_before_reading_new_html_file() -> None:
    data_dir = _fresh_data_dir()
    manifest_path = data_dir / "manifest.json"
    new_html = data_dir / "sop-new.html"
    new_html.write_text(
        "<html><head><title>新增 SOP</title></head><body><p>新增文件 关键指标 Round15Token</p></body></html>",
        encoding="utf-8",
    )

    manifest_json = update_manifest(data_dir=data_dir, manifest_path=manifest_path)
    manifest = json.loads(manifest_json)

    logger.info("updated_manifest=%s", manifest)
    assert manifest_path.read_text(encoding="utf-8") == manifest_json
    assert manifest[0]["doc_id"] == "sop-new"
    assert manifest[0]["filename"] == "sop-new.html"
    assert manifest[0]["title"] == "新增 SOP"
    assert {"新增", "SOP", "关键指标", "Round15Token"}.issubset(manifest[0]["keywords"])


def test_manifest_builder_skips_non_html_and_unsafe_file_names() -> None:
    data_dir = _fresh_data_dir()
    manifest_path = data_dir / "manifest.json"
    (data_dir / "sop-001.html").write_text(
        "<html><head><title>Allowed SOP</title></head><body>Allowed Keyword</body></html>",
        encoding="utf-8",
    )
    (data_dir / "domain_dictionary.json").write_text("{}", encoding="utf-8")
    unsafe_dir = data_dir / "nested"
    unsafe_dir.mkdir()
    (unsafe_dir / "sop-002.html").write_text(
        "<html><body>nested</body></html>",
        encoding="utf-8",
    )

    manifest = json.loads(update_manifest(data_dir=data_dir, manifest_path=manifest_path))

    logger.info("filtered_manifest=%s", manifest)
    assert [entry["filename"] for entry in manifest] == ["sop-001.html"]
