import pytest
from app.database.repositories import (
    create_ticket,
    get_ticket,
    update_ticket_status,
    create_run,
    get_run,
    update_run_state,
    get_or_create_repository
)
from app.memory.flywheel import failure_flywheel
from app.integrations.graph.adapter import meta_graph_adapter

def test_sqlite_persistence_lifecycle(test_db):
    # 1. Register Repository
    repo = get_or_create_repository(
        test_db,
        repo_id="test_repo",
        name="Test Repository",
        path="E:/MM Office/Agent Chess",
        commit_hash="abc1234"
    )
    assert repo.id == "test_repo"

    # 2. Create Ticket
    ticket = create_ticket(test_db, {
        "repo_id": "test_repo",
        "title": "Add retry telemetry to groq_agent",
        "problem_statement": "Retry count not tracked.",
        "motivation": "Improve monitoring.",
        "current_behavior": "None",
        "desired_behavior": "Tracked",
        "acceptance_criteria_json": ["Retry count stored"],
        "proposed_tests_json": ["test_retry()"],
        "candidate_files_json": ["backend/app/agents/groq_agent.py"],
        "status": "PROPOSED"
    })
    assert ticket.id.startswith("ouro-")
    assert ticket.status == "PROPOSED"

    # 3. Update Status
    updated = update_ticket_status(test_db, ticket.id, "APPROVED")
    assert updated.status == "APPROVED"

    # 4. Create Run
    run = create_run(test_db, {
        "ticket_id": ticket.id,
        "repo_id": "test_repo",
        "state": "IDLE"
    })
    assert run.state == "IDLE"

    # 5. Transition Run
    run_up = update_run_state(test_db, run.id, "CODING", active_agent="LocalCoder")
    assert run_up.state == "CODING"
    assert run_up.active_agent == "LocalCoder"

def test_failure_flywheel_persistence_and_deduplication(test_db):
    # Record first failure
    traj1 = failure_flywheel.record_failure(
        db=test_db,
        run_id="run-1",
        ticket_id="ticket-101",
        attempt=1,
        failed_tests=["test_telemetry_recording"],
        traceback_excerpt="AssertionError: assert None == 1",
        ast_diff={"sample.py": {"modified": ["calculate"]}},
        patch_hash="hash_attempt_1",
        root_cause_hypothesis="Variable not assigned",
        repair_hint="Initialize variable before return",
        provider="ollama",
        model="qwen2.5-coder:1.5b"
    )
    assert traj1.status == "UNRESOLVED"

    # Retrieve context for repair agent
    ctx = failure_flywheel.get_repair_context(test_db, "ticket-101")
    assert ctx["has_history"] is True
    assert len(ctx["prior_attempts"]) == 1
    assert "AssertionError" in ctx["prior_attempts"][0]["traceback"]

    # Record second identical failure (same patch hash + same failed test) -> REPEATED!
    traj2 = failure_flywheel.record_failure(
        db=test_db,
        run_id="run-1",
        ticket_id="ticket-101",
        attempt=2,
        failed_tests=["test_telemetry_recording"],
        traceback_excerpt="AssertionError: assert None == 1",
        ast_diff={"sample.py": {"modified": ["calculate"]}},
        patch_hash="hash_attempt_1",
        root_cause_hypothesis="Still failing",
        repair_hint="Different strategy required",
        provider="ollama",
        model="qwen2.5-coder:1.5b"
    )
    assert traj2.status == "REPEATED"

    # Export to JSON
    json_out = failure_flywheel.export_trajectories_json(test_db, "ticket-101")
    assert "AssertionError" in json_out
    assert "ticket-101" in json_out

@pytest.mark.asyncio
async def test_meta_graph_adapter_agent_chess():
    # Test checking connection on actual indexed file
    status = await meta_graph_adapter.check_connection("agent_chess")
    assert status["connected"] is True
    assert status["node_count"] > 100
    assert status["edge_count"] > 200

    # Test file dependency query
    deps = meta_graph_adapter.get_file_dependencies("agent_chess", "backend/app/agents/groq_agent.py")
    assert deps["found"] is True
    assert len(deps["symbols"]) > 0

    # Test associated test query
    tests = meta_graph_adapter.get_associated_tests("agent_chess", ["backend/app/agents/groq_agent.py"])
    assert len(tests) > 0

def test_evaluation_metrics_and_benchmark_api(test_db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database.session import get_db

    # Override get_db to use test_db
    app.dependency_overrides[get_db] = lambda: test_db
    client = TestClient(app)

    try:
        # Test GET /api/evaluation/metrics
        res_metrics = client.get("/api/evaluation/metrics")
        assert res_metrics.status_code == 200
        metrics_data = res_metrics.json()
        assert "repair_success_rate" in metrics_data
        assert "candidate_test_pass_rate" in metrics_data
        assert "regression_rate" in metrics_data
        assert "total_runs" in metrics_data

        # Test GET /api/evaluation/benchmark/tasks
        res_tasks = client.get("/api/evaluation/benchmark/tasks")
        assert res_tasks.status_code == 200
        tasks_data = res_tasks.json()
        assert len(tasks_data) >= 3
        task_ids = [t["task_id"] for t in tasks_data]
        assert "BENCH-01" in task_ids
        assert "BENCH-02" in task_ids
        assert "BENCH-03" in task_ids
    finally:
        app.dependency_overrides.clear()

