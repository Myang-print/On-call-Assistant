import json
import logging

import pytest


logger = logging.getLogger(__name__)


def test_read_file_reads_named_file_from_data_directory() -> None:
    from app.tool_runtime import readFile

    content = readFile("sop-001.html")

    logger.info("read_file_prefix=%s", content[:80])
    assert "后端服务 On-Call SOP" in content
    assert "OOM" in content


def test_read_file_updates_then_reads_manifest_file() -> None:
    from app.tool_runtime import readFile

    manifest = json.loads(readFile("manifest.json"))

    logger.info("manifest=%s", manifest)
    assert len(manifest) == 10
    assert set(manifest[0]) == {"doc_id", "filename", "title", "keywords"}
    assert manifest[0]["doc_id"] == "sop-001"
    assert manifest[0]["filename"] == "sop-001.html"
    assert manifest[0]["title"] == "后端服务 On-Call SOP"
    assert "OOM" in manifest[0]["keywords"]
    assert [entry["doc_id"] for entry in manifest] == [
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


@pytest.mark.parametrize("filename", ["", "   "])
def test_read_file_rejects_empty_filename(filename: str) -> None:
    from app.tool_runtime import readFile

    with pytest.raises(ValueError, match="filename is required"):
        readFile(filename)


@pytest.mark.parametrize("filename", [".", "sop-001.html/child"])
def test_read_file_rejects_directory_reads(filename: str) -> None:
    from app.tool_runtime import readFile

    with pytest.raises(ValueError, match="filename only"):
        readFile(filename)


@pytest.mark.parametrize("filename", ["*.html", "sop-00?.html", "[abc].html"])
def test_read_file_rejects_wildcards(filename: str) -> None:
    from app.tool_runtime import readFile

    with pytest.raises(ValueError, match="wildcards are not allowed"):
        readFile(filename)


@pytest.mark.parametrize("filename", ["../README.md", "..\\README.md", "subdir/file.html"])
def test_read_file_rejects_paths_outside_data_directory(filename: str) -> None:
    from app.tool_runtime import readFile

    with pytest.raises(ValueError, match="filename only"):
        readFile(filename)


def test_read_file_rejects_missing_data_file() -> None:
    from app.tool_runtime import readFile

    with pytest.raises(FileNotFoundError):
        readFile("data")


def test_read_file_rejects_json_files_except_manifest() -> None:
    from app.tool_runtime import readFile

    with pytest.raises(ValueError, match="json files are not allowed"):
        readFile("domain_dictionary.json")


def test_tool_runtime_import_does_not_load_search_modules() -> None:
    import sys

    sys.modules.pop("app.tool_runtime", None)
    sys.modules.pop("app.key_search", None)
    sys.modules.pop("app.semantic_search", None)
    sys.modules.pop("app.hybrid_search", None)
    import app.tool_runtime as module

    logger.info("tool_runtime_module=%s", module)
    assert "app.key_search" not in sys.modules
    assert "app.semantic_search" not in sys.modules
    assert "app.hybrid_search" not in sys.modules
