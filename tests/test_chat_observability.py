from __future__ import annotations

import json
import asyncio
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    assert re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])
    assert float(response.headers["x-response-time-ms"]) >= 0
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert {event["correlation_id"] for event in events} == {response.headers["x-request-id"]}
    request_event = next(event for event in events if event["event"] == "request_received")
    assert request_event["user_id_hash"]
    assert request_event["session_id"] == "session-01"
    assert request_event["feature"] == "qa"
    assert request_event["model"]
    assert request_event["env"]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_valid_request_id_is_reused() -> None:
    async def send_request() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/health", headers={"x-request-id": "req-ABCDEF12"})

    response = asyncio.run(send_request())
    assert response.headers["x-request-id"] == "req-abcdef12"
