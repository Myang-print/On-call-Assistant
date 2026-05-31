import logging

from app.agent_runtime import run_deterministic_agent


logger = logging.getLogger(__name__)


def _successful_read_filenames(result: dict[str, object]) -> list[str]:
    filenames: list[str] = []
    for event in result["trace"]:
        action = event["action"]
        observation = event["observation"]
        if action["type"] == "readFile" and observation["ok"] is True:
            filenames.append(action["fname"])
    return filenames


def test_runtime_reads_selected_sop_and_builds_docs_from_successful_readfile() -> None:
    result = run_deterministic_agent(max_step=5, query="服务 OOM 了怎么办？")

    logger.info("oom_runtime_result=%s", result)
    successful_reads = _successful_read_filenames(result)
    source_filenames = [source["filename"] for source in result["sources"]]
    doc_filenames = [document["filename"] for document in result["retrieved_docs"]]

    assert result["status"] == "finished"
    assert "manifest.json" in successful_reads
    assert "sop-001.html" in successful_reads
    assert source_filenames[0] == "sop-001.html"
    assert source_filenames == doc_filenames
    assert set(source_filenames).issubset(set(successful_reads))


def test_runtime_does_not_add_failed_sop_read_to_sources_or_docs() -> None:
    def partial_read_file(filename: str) -> str:
        if filename == "manifest.json":
            return (
                '[{"doc_id":"sop-001","filename":"sop-001.html","title":"后端服务 On-Call SOP",'
                '"keywords":["OOM","后端服务"]}]'
            )
        raise FileNotFoundError(filename)

    result = run_deterministic_agent(
        max_step=4,
        query="服务 OOM 了怎么办？",
        tools={"readFile": partial_read_file},
    )

    logger.info("failed_sop_runtime_result=%s", result)
    assert result["status"] == "finished"
    assert result["retrieved_docs"] == []
    assert result["sources"] == []
    assert result["trace"][1]["action"] == {"type": "readFile", "fname": "sop-001.html"}
    assert result["trace"][1]["observation"]["ok"] is False
    assert result["trace"][1]["observation"]["accepted_as_source"] is False
    assert result["trace"][1]["observation"]["reject_reason"] == "read_failed"


def test_runtime_records_source_acceptance_for_every_readfile() -> None:
    result = run_deterministic_agent(max_step=5, query="服务 OOM 了怎么办？")

    read_events = [event for event in result["trace"] if event["action"]["type"] == "readFile"]

    assert read_events
    for event in read_events:
        assert "accepted_as_source" in event["observation"]
        if event["observation"]["accepted_as_source"] is False:
            assert "reject_reason" in event["observation"]

    assert read_events[0]["action"]["fname"] == "manifest.json"
    assert read_events[0]["observation"]["accepted_as_source"] is False
    assert read_events[0]["observation"]["reject_reason"] == "manifest_not_source"


def test_runtime_rejects_source_without_successful_readfile_trace() -> None:
    result = run_deterministic_agent(max_step=5, query="数据库主从延迟超过30秒怎么处理？")
    successful_reads = set(_successful_read_filenames(result))

    for source in result["sources"]:
        assert source["filename"] in successful_reads


def test_runtime_rejects_inauthentic_sop_content_from_sources() -> None:
    def mismatched_read_file(filename: str) -> str:
        if filename == "manifest.json":
            return (
                '[{"doc_id":"sop-001","filename":"sop-001.html","title":"后端服务 On-Call SOP",'
                '"keywords":["OOM","后端服务"]}]'
            )
        if filename == "sop-001.html":
            return "<html><head><title>伪造 SOP</title></head><body>fake content</body></html>"
        raise FileNotFoundError(filename)

    result = run_deterministic_agent(
        max_step=4,
        query="服务 OOM 了怎么办？",
        tools={"readFile": mismatched_read_file},
    )

    logger.info("inauthentic_sop_runtime_result=%s", result)
    assert result["retrieved_docs"] == []
    assert result["sources"] == []
    assert result["trace"][1]["observation"]["ok"] is True
    assert result["trace"][1]["observation"]["accepted_as_source"] is False
    assert result["trace"][1]["observation"]["reject_reason"] == "title_mismatch"


def test_runtime_does_not_read_unsafe_manifest_filename() -> None:
    tool_calls: list[str] = []

    def unsafe_manifest_read_file(filename: str) -> str:
        tool_calls.append(filename)
        if filename == "manifest.json":
            return (
                '[{"doc_id":"unsafe","filename":"../sop-001.html","title":"后端服务 On-Call SOP",'
                '"keywords":["OOM","后端服务"]}]'
            )
        raise AssertionError(f"unsafe file should not be read: {filename}")

    result = run_deterministic_agent(
        max_step=4,
        query="服务 OOM 了怎么办？",
        tools={"readFile": unsafe_manifest_read_file},
    )

    assert tool_calls == ["manifest.json"]
    assert result["retrieved_docs"] == []
    assert result["sources"] == []


def test_runtime_selects_expected_sops_from_manifest_light_fields() -> None:
    cases = [
        ("数据库主从延迟超过30秒怎么处理？", "sop-002.html"),
        ("怀疑有人入侵了系统", "sop-005.html"),
        ("推荐结果质量下降了", "sop-008.html"),
    ]

    for query, expected_filename in cases:
        result = run_deterministic_agent(max_step=5, query=query)
        successful_reads = _successful_read_filenames(result)

        logger.info("query=%s runtime_result=%s", query, result)
        assert expected_filename in successful_reads
        assert result["sources"][0]["filename"] == expected_filename
