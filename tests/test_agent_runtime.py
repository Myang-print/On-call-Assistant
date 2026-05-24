import logging

from app.agent_runtime import AgentState, run_deterministic_agent, select_action


logger = logging.getLogger(__name__)


def test_agent_state_defaults_to_safe_initial_state() -> None:
    state = AgentState(max_step=3)

    logger.info("initial_state=%s", state)
    assert state.max_step == 3
    assert state.step == 0
    assert state.history == []


def test_select_action_depends_only_on_step() -> None:
    assert select_action(AgentState(max_step=3, step=0, history=[])) == {
        "type": "readFile",
        "fname": "manifest.json",
    }
    assert select_action(AgentState(max_step=3, step=1, history=[])) == {
        "type": "finish",
        "message": "deterministic runtime complete",
    }


def test_run_deterministic_agent_records_trace_and_finishes_safely() -> None:
    result = run_deterministic_agent(max_step=3)

    logger.info("agent_result=%s", result)
    assert result["status"] == "finished"
    assert result["state"].step == 2
    assert [event["action"]["type"] for event in result["trace"]] == ["readFile", "finish"]
    assert result["trace"][0]["step"] == 0
    assert result["trace"][0]["observation"]["ok"] is True
    assert result["trace"][0]["observation"]["tool"] == "readFile"
    assert result["trace"][1]["step"] == 1


def test_run_deterministic_agent_stops_at_max_step_before_next_action() -> None:
    result = run_deterministic_agent(max_step=1)

    logger.info("limited_agent_result=%s", result)
    assert result["status"] == "max_step_reached"
    assert result["state"].step == 1
    assert len(result["trace"]) == 1
    assert result["trace"][0]["action"]["type"] == "readFile"
