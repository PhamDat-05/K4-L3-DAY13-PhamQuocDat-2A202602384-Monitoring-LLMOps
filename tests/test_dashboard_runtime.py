from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import logging_config
from app.dashboard import dashboard_data


def test_dashboard_aggregates_real_log_events(monkeypatch, tmp_path: Path) -> None:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    ts = (now - timedelta(minutes=5)).isoformat()
    records = [
        {"ts": ts, "event": "request_received"},
        {"ts": ts, "event": "response_sent", "latency_ms": 200, "ttft_ms": 50, "cost_usd": 0.002, "tokens_in": 25, "tokens_out": 75, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": True},
        {"ts": ts, "event": "request_received"},
        {"ts": ts, "event": "request_failed", "error_type": "RuntimeError", "tool_name": "retrieval", "tool_success": False},
    ]
    path = tmp_path / "logs.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    monkeypatch.setattr(logging_config, "LOG_PATH", path)

    data = dashboard_data(now)
    panels = {panel["id"]: panel["values"] for panel in data["panels"]}
    assert len(panels) == 6
    assert panels["latency"]["p95"] == 200
    assert panels["traffic"]["count"] == 2
    assert panels["errors"]["error_rate_pct"] == 50
    assert panels["errors"]["retrieval_success_pct"] == 50
    assert panels["cost"]["total"] == 0.002
    assert panels["tokens"] == {"input": 25, "output": 75}
    assert panels["quality"]["mean"] == 0.8
