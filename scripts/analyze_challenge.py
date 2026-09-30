"""Build CP3 evidence from the coach's unchanged challenge, logs and Langfuse."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from app.challenge import load_challenge  # noqa: E402
from app.metrics import percentile  # noqa: E402

EVIDENCE = REPO_ROOT / "submission" / "evidence"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"


def run_ids(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8-sig")
    if "Challenge:" not in content or "[200]" not in content:
        raise ValueError(f"Challenge workload failed: {path.name}")
    return re.findall(r"\[200\] (req-[0-9a-f]{8})", content)


def matched_logs() -> tuple[dict, dict[str, list[dict]], dict[str, list[dict]], dict[str, list[dict]]]:
    challenge = load_challenge(REPO_ROOT / "config" / "challenge.json")
    if challenge.cohort != "K4" or "k4-l3b" not in challenge.challenge_id.lower():
        raise ValueError("Challenge does not belong to K4-L3B")
    baseline_ids = run_ids(EVIDENCE / "12a-challenge-baseline.txt")
    incident_ids = run_ids(EVIDENCE / "12c-challenge-load.txt")
    recovery_ids = run_ids(EVIDENCE / "12e-challenge-recovery.txt")
    if any(len(ids) != len(challenge.queries) for ids in (baseline_ids, incident_ids, recovery_ids)):
        raise ValueError("Challenge response count does not match the coach's query count")
    if len(set(baseline_ids + incident_ids + recovery_ids)) != len(baseline_ids + incident_ids + recovery_ids):
        raise ValueError("Correlation IDs are not unique")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        cid = record.get("correlation_id")
        if cid in baseline_ids or cid in incident_ids or cid in recovery_ids:
            grouped[cid].append(record)

    def extract(ids: list[str]) -> dict[str, list[dict]]:
        result = {cid: grouped[cid] for cid in ids}
        for cid, records in result.items():
            if sum(r.get("event") == "request_received" for r in records) != 1:
                raise ValueError(f"Missing request_received for {cid}")
            if sum(r.get("event") == "response_sent" for r in records) != 1:
                raise ValueError(f"Missing response_sent for {cid}")
        return result

    return challenge, extract(baseline_ids), extract(incident_ids), extract(recovery_ids)


def response(records: list[dict]) -> dict:
    return next(r for r in records if r["event"] == "response_sent")


def metrics(challenge, baseline: dict, incident: dict, recovery: dict) -> None:
    print(f"Challenge ID: {challenge.challenge_id} | cohort: {challenge.cohort} | affected feature: {challenge.affected_feature}")
    print(f"Latency threshold from coach's challenge: {challenge.latency_threshold_ms} ms")
    for label, group in (("baseline", baseline), ("incident", incident), ("recovery", recovery)):
        received = [next(r for r in rows if r["event"] == "request_received") for rows in group.values()]
        sent = [response(rows) for rows in group.values()]
        latencies = [r["latency_ms"] for r in sent]
        ttfts = [r["ttft_ms"] for r in sent]
        times = [r["ts"] for r in received + sent]
        slow = sum(value > challenge.latency_threshold_ms for value in latencies)
        print(
            f"{label}: window_utc={min(times)}..{max(times)} requests={len(received)} "
            f"responses={len(sent)} errors=0 above_{challenge.latency_threshold_ms}ms={slow}/{len(sent)} "
            f"latency_p50_ms={percentile(latencies, 50):.0f} "
            f"latency_p95_ms={percentile(latencies, 95):.0f} "
            f"latency_p99_ms={percentile(latencies, 99):.0f} "
            f"ttft_p95_ms={percentile(ttfts, 95):.0f} "
            f"avg_cost_usd={mean(r['cost_usd'] for r in sent):.6f}"
        )
    baseline_p95 = percentile([response(rows)["latency_ms"] for rows in baseline.values()], 95)
    incident_p95 = percentile([response(rows)["latency_ms"] for rows in incident.values()], 95)
    recovery_p95 = percentile([response(rows)["latency_ms"] for rows in recovery.values()], 95)
    print(f"P95 change: +{incident_p95 - baseline_p95:.0f} ms ({incident_p95 / baseline_p95:.2f}x)")
    print(f"P95 after disabling incident: {recovery_p95:.0f} ms ({incident_p95 - recovery_p95:.0f} ms lower than incident)")
    for cid, records in incident.items():
        r = response(records)
        print(f"incident_log: ts={r['ts']} correlation_id={cid} latency_ms={r['latency_ms']} ttft_ms={r['ttft_ms']} trace_id={r['trace_id']} tool_success={r['tool_success']}")


def duration_ms(observation) -> float:
    if observation.end_time is None:
        raise ValueError(f"Observation {observation.name} has no end time")
    return (observation.end_time - observation.start_time).total_seconds() * 1000


def traces(challenge, baseline: dict, incident: dict) -> None:
    from langfuse import get_client

    client = get_client()
    projects = {project.id: project.name for project in client.api.projects.get().data}
    spans: dict[str, list[float]] = {"baseline": [], "incident": []}
    projects_seen: set[str] = set()
    representative = None
    for label, group in (("baseline", baseline), ("incident", incident)):
        for cid, records in group.items():
            trace_id = response(records).get("trace_id")
            if not re.fullmatch(r"[0-9a-f]{32}", trace_id or ""):
                raise ValueError(f"Invalid trace ID in log for {cid}")
            observations = client.api.observations.get_many(
                trace_id=trace_id,
                fields="core,basic,metadata,model,usage,prompt,metrics",
                limit=20,
            ).data
            by_name = {observation.name: observation for observation in observations}
            if set(by_name) != {"lab-agent-run", "retrieval", "generation"}:
                raise ValueError(f"Incomplete Langfuse trace {trace_id}: {sorted(by_name)}")
            root, retrieval, generation = (by_name[name] for name in ("lab-agent-run", "retrieval", "generation"))
            if retrieval.parent_observation_id != root.id or generation.parent_observation_id != root.id:
                raise ValueError(f"Broken trace parentage for {trace_id}")
            if any((observation.metadata or {}).get("correlation_id") != cid for observation in observations):
                raise ValueError(f"Log/trace correlation mismatch for {trace_id}")
            projects_seen.add(root.project_id)
            retrieval_ms = duration_ms(retrieval)
            generation_ms = duration_ms(generation)
            spans[label].append(retrieval_ms)
            print(
                f"{label}: correlation_id={cid} trace_id={trace_id} "
                f"root_ms={duration_ms(root):.1f} retrieval_ms={retrieval_ms:.1f} "
                f"generation_ms={generation_ms:.1f} prompt={generation.prompt_name} v{generation.prompt_version} "
                f"tokens={generation.usage_details} cost_usd={generation.total_cost}"
            )
            if label == "incident" and representative is None:
                representative = (cid, trace_id, root, retrieval, generation)

    if len(projects_seen) != 1:
        raise ValueError("Traces span multiple projects")
    project_id = next(iter(projects_seen))
    print(f"Project: {projects.get(project_id, project_id)}")
    print(f"Retrieval P95: baseline={percentile(spans['baseline'], 95):.1f} ms incident={percentile(spans['incident'], 95):.1f} ms")
    if representative is not None:
        cid, trace_id, root, retrieval, generation = representative
        print(f"Representative: correlation_id={cid} trace_id={trace_id}")
        for observation in (root, retrieval, generation):
            print(
                f"  {observation.name}: id={observation.id} parent={observation.parent_observation_id} "
                f"type={observation.type} duration_ms={duration_ms(observation):.1f} "
                f"level={observation.level}"
            )
        import os

        base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").rstrip("/")
        print(f"Trace URL: {base_url}/project/{project_id}/traces/{trace_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", choices=["metrics", "traces"], required=True)
    args = parser.parse_args()
    challenge, baseline, incident, recovery = matched_logs()
    if args.part == "metrics":
        metrics(challenge, baseline, incident, recovery)
    else:
        traces(challenge, baseline, incident)
    return 0


if __name__ == "__main__":
    sys.exit(main())
