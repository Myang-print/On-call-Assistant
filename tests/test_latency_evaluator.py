from eval.latency_evaluator import format_latency_table, summarize_latency_runs


def test_summarize_latency_runs_reports_latency_answer_length_and_fallback_rate() -> None:
    runs = [
        {
            "query": "服务 OOM 了怎么办？",
            "trace": [
                {"event": "prompt_built", "prompt_chars": 900},
                {"event": "llm_call_succeeded", "answer_chars": 300, "elapsed_seconds": 12.5},
            ],
        },
        {
            "query": "数据库主从延迟超过30秒怎么处理？",
            "trace": [
                {"event": "prompt_built", "prompt_chars": 700},
                {"event": "llm_call_failed", "elapsed_seconds": 90.0},
                {"event": "deterministic_fallback"},
            ],
            "answer": "fallback answer",
        },
    ]

    summary = summarize_latency_runs(runs)

    assert summary["case_count"] == 2
    assert summary["average_prompt_chars"] == 800
    assert summary["average_answer_chars"] == 157.5
    assert summary["average_elapsed_seconds"] == 51.25
    assert summary["success_rate"] == 0.5
    assert summary["fallback_rate"] == 0.5
    assert summary["rows"] == [
        {
            "query": "服务 OOM 了怎么办？",
            "prompt_chars": 900,
            "answer_chars": 300,
            "elapsed_seconds": 12.5,
            "llm_success": True,
            "fallback_used": False,
        },
        {
            "query": "数据库主从延迟超过30秒怎么处理？",
            "prompt_chars": 700,
            "answer_chars": 15,
            "elapsed_seconds": 90.0,
            "llm_success": False,
            "fallback_used": True,
        },
    ]


def test_format_latency_table_prints_required_columns() -> None:
    summary = {
        "average_elapsed_seconds": 12.5,
        "average_answer_chars": 300,
        "success_rate": 1.0,
        "fallback_rate": 0.0,
        "rows": [
            {
                "query": "服务 OOM 了怎么办？",
                "prompt_chars": 900,
                "answer_chars": 300,
                "elapsed_seconds": 12.5,
                "llm_success": True,
                "fallback_used": False,
            }
        ],
    }

    table = format_latency_table(summary)

    assert "query | prompt_chars | answer_chars | elapsed_seconds | llm_success | fallback_used" in table
    assert "服务 OOM 了怎么办？ | 900 | 300 | 12.5 | True | False" in table
    assert "average_elapsed_seconds: 12.5" in table
    assert "fallback_rate: 0.0" in table
