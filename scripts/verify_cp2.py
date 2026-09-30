"""Verify that local CP2 log IDs resolve to real Langfuse observation trees."""

from __future__ import annotations

import re
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

from langfuse import get_client  # noqa: E402

WORKFLOW = REPO_ROOT / "submission" / "evidence" / "09-10-prompt-workflow.txt"


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8-sig")
    versions = re.search(r"baseline v(\d+); candidate v(\d+)", text)
    if versions is None:
        raise ValueError("Missing prompt version evidence")
    baseline_version, candidate_version = map(int, versions.groups())
    entries = re.findall(r"label=([\w-]+) correlation_id=(req-[0-9a-f]{8}) trace_id=([0-9a-f]{32})", text)
    if len(entries) < 10:
        raise ValueError("Fewer than 10 intact trace IDs in workflow evidence")

    client = get_client()
    project_names = {p.id: p.name for p in client.api.projects.get().data}
    checked = 0
    project_ids: set[str] = set()
    for label, correlation_id, trace_id in entries:
        for attempt in range(3):
            observations = client.api.observations.get_many(
                trace_id=trace_id,
                fields="core,basic,metadata,model,usage,prompt,metrics",
                limit=20,
            ).data
            if len(observations) >= 3 or attempt == 2:
                break
            time.sleep(2)
        by_name = {observation.name: observation for observation in observations}
        if set(by_name) != {"lab-agent-run", "retrieval", "generation"}:
            raise ValueError(f"Incomplete observation tree for {trace_id}: {sorted(by_name)}")
        root, retrieval, generation = (by_name[name] for name in ("lab-agent-run", "retrieval", "generation"))
        if not (root.type == "AGENT" and retrieval.type == "RETRIEVER" and generation.type == "GENERATION"):
            raise ValueError(f"Wrong observation types for {trace_id}")
        if retrieval.parent_observation_id != root.id or generation.parent_observation_id != root.id:
            raise ValueError(f"Broken parent-child tree for {trace_id}")
        if any((observation.metadata or {}).get("correlation_id") != correlation_id for observation in observations):
            raise ValueError(f"Correlation ID mismatch for {trace_id}")
        expected_version = candidate_version if label in {"candidate", "production-promoted"} else baseline_version
        if generation.prompt_name != "day13-chat" or generation.prompt_version != expected_version:
            raise ValueError(f"Wrong linked prompt for {trace_id}")
        metadata = generation.metadata or {}
        expected_label = label if label in {"baseline", "candidate"} else "production"
        if (
            metadata.get("prompt_label") != expected_label
            or str(metadata.get("prompt_version")) != str(expected_version)
            or metadata.get("prompt_source") != "langfuse"
        ):
            raise ValueError(f"Wrong prompt metadata for {trace_id}")
        if not (generation.usage_details or {}).get("input") or not (generation.usage_details or {}).get("output"):
            raise ValueError(f"Missing token usage for {trace_id}")
        if not generation.total_cost or generation.total_cost <= 0:
            raise ValueError(f"Missing cost for {trace_id}")
        project_ids.add(root.project_id)
        checked += 1
        print(f"{label}: {trace_id} / {correlation_id} / prompt v{generation.prompt_version} label={expected_label} / root>retrieval+generation OK")
        if checked == 1:
            print(f"Generation model={generation.model}, usage={generation.usage_details}, cost_usd={generation.total_cost}, prompt_name={generation.prompt_name}")

    if len(project_ids) != 1:
        raise ValueError("Traces span more than one project")
    project_id = next(iter(project_ids))
    print(f"Project: {project_names.get(project_id, project_id)}")
    base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").rstrip("/")
    print(f"Example trace URL: {base_url}/project/{project_id}/traces/{entries[0][2]}")
    print(f"Verified Langfuse traces: {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
