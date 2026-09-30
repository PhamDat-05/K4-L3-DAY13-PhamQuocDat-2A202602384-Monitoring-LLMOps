"""Create a repeatable personal-project prompt rollback and traced workload."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from app.main import app  # noqa: E402 - dotenv must be loaded first
from app.logging_config import LOG_PATH  # noqa: E402
from app.tracing import get_langfuse_client  # noqa: E402


def fetch_label(client, name: str, label: str):
    try:
        return client.get_prompt(name, label=label, cache_ttl_seconds=0, max_retries=0)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            return None
        raise


def labels_with(prompt, label: str) -> list[str]:
    # Langfuse assigns `latest` itself and rejects it in update_prompt.
    return sorted((set(getattr(prompt, "labels", []) or []) - {"latest"}) | {label})


def trace_for(correlation_id: str) -> str | None:
    if not LOG_PATH.exists():
        return None
    for line in reversed(LOG_PATH.read_text(encoding="utf-8").splitlines()):
        record = json.loads(line)
        if record.get("event") == "response_sent" and record.get("correlation_id") == correlation_id:
            return record.get("trace_id")
    return None


async def send(payload: dict, label: str) -> tuple[str, str | None]:
    os.environ["LANGFUSE_PROMPT_LABEL"] = label
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://lab") as http:
        response = await http.post("/chat", json=payload, timeout=30)
    response.raise_for_status()
    cid = response.json()["correlation_id"]
    return cid, trace_for(cid)


async def main() -> None:
    client = get_langfuse_client()
    if not client.auth_check():
        raise RuntimeError("Langfuse authentication failed")
    os.environ["LANGFUSE_PROMPT_CACHE_TTL_SECONDS"] = "0"
    name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    template = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"

    baseline = fetch_label(client, name, "baseline")
    if baseline is None:
        production = fetch_label(client, name, "production")
        if production is None:
            baseline = client.create_prompt(name=name, type="text", prompt=template, labels=["baseline", "production"])
        else:
            baseline = production
            client.update_prompt(name=name, version=baseline.version, new_labels=labels_with(baseline, "baseline"))
    candidate = fetch_label(client, name, "candidate")
    if candidate is None:
        candidate = client.create_prompt(
            name=name,
            type="text",
            prompt=template + "\nAnswer briefly using the retrieved context.",
            labels=["candidate"],
        )
    print(f"Prompt {name}: baseline v{baseline.version}; candidate v{candidate.version}")

    payloads = [json.loads(line) for line in (REPO_ROOT / "data" / "sample_queries.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for label in ("baseline", "candidate"):
        cid, trace_id = await send(payloads[0], label)
        print(f"label={label} correlation_id={cid} trace_id={trace_id}")

    try:
        client.update_prompt(name=name, version=candidate.version, new_labels=labels_with(candidate, "production"))
        promoted = fetch_label(client, name, "production")
        print(f"Promoted production -> v{promoted.version}")
        cid, trace_id = await send(payloads[0], "production")
        print(f"label=production-promoted correlation_id={cid} trace_id={trace_id}")
    finally:
        current_baseline = client.get_prompt(name, version=baseline.version, cache_ttl_seconds=0)
        client.update_prompt(name=name, version=baseline.version, new_labels=labels_with(current_baseline, "production"))
        rolled_back = fetch_label(client, name, "production")
        print(f"Rolled back production -> v{rolled_back.version}")
    cid, trace_id = await send(payloads[0], "production")
    print(f"label=production-rollback correlation_id={cid} trace_id={trace_id}")

    for payload in payloads[1:]:
        cid, trace_id = await send(payload, "production")
        print(f"label=production correlation_id={cid} trace_id={trace_id}")
    client.flush()
    print("Flushed traces to Langfuse")


if __name__ == "__main__":
    asyncio.run(main())
