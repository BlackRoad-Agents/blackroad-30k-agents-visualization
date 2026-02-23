"""Tests for BlackRoad Visualization."""
import json, os, sys
from pathlib import Path
import pytest

os.environ["VIZ_DB"] = "/tmp/test_viz.db"
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from visualization import (
    get_conn, seed_simulation, get_node_stats, get_distribution,
    get_capacity_metrics, get_live_states, generate_chart_data, snapshot,
    LiveAgentState, _now,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "viz.db"
    monkeypatch.setenv("VIZ_DB", str(db))
    import visualization
    visualization.DB_PATH = db
    yield


def test_seed_creates_nodes():
    conn = get_conn()
    seed_simulation(conn)
    nodes = get_node_stats(conn)
    assert len(nodes) == 5
    assert any(n.hostname == "octavia-pi" for n in nodes)


def test_distribution_type_sums_to_30k():
    conn = get_conn()
    seed_simulation(conn)
    buckets = get_distribution(conn, "type")
    total = sum(b.count for b in buckets)
    # Allow ±100 for rounding
    assert abs(total - 30_000) < 200


def test_capacity_fill_pct():
    conn = get_conn()
    seed_simulation(conn)
    metrics = get_capacity_metrics(conn)
    for m in metrics:
        assert 0.0 <= m.fill_pct() <= 100.0


def test_live_states_status_filter():
    conn = get_conn()
    seed_simulation(conn)
    states = get_live_states(conn, status_filter="online")
    assert all(s.status == "online" for s in states)


def test_generate_chart_data():
    conn = get_conn()
    seed_simulation(conn)
    chart = generate_chart_data(conn, "type_distribution")
    d = chart.to_dict()
    assert "labels" in d
    assert isinstance(d["labels"], list)
    assert len(d["datasets"]) > 0


def test_snapshot_structure():
    conn = get_conn()
    seed_simulation(conn)
    data = snapshot(conn)
    assert data["total_agents"] == 30_000
    assert "nodes" in data
    assert "by_status" in data
    assert "by_type" in data


def test_live_agent_stale_detection():
    from datetime import timedelta
    old_hb = ((__import__("datetime").datetime.utcnow()) - timedelta(seconds=400)).isoformat(timespec="seconds")
    state = LiveAgentState(
        state_id="x", agent_id="a1", agent_type="worker", status="online",
        node_id="node1", task_count=0, error_count=0,
        last_heartbeat=old_hb, latency_ms=10.0,
    )
    assert state.is_stale(threshold_seconds=300) is True


def test_node_health_critical():
    from visualization import NodeStats
    n = NodeStats(node_id="n", hostname="h", ip="1.2.3.4", role="PRIMARY",
                  capacity=100, active_agents=96, idle_agents=2, busy_agents=2,
                  offline_agents=0, cpu_pct=50.0, mem_pct=50.0, net_mbps=100.0,
                  recorded_at=_now())
    assert n.health() == "critical"
