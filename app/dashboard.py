"""Live six-panel dashboard computed from the structured JSONL log."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from . import logging_config
from .metrics import percentile

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "dashboard.yaml"


def dashboard_data(now: datetime | None = None) -> dict[str, Any]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(minutes=config["time_range_minutes"])
    records: list[dict[str, Any]] = []
    if logging_config.LOG_PATH.exists():
        for line in logging_config.LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
                if start <= timestamp <= end:
                    record["_minute"] = timestamp.strftime("%H:%M")
                    records.append(record)
            except (ValueError, KeyError, TypeError):
                continue

    received = [r for r in records if r.get("event") == "request_received"]
    responses = [r for r in records if r.get("event") == "response_sent"]
    failures = [r for r in records if r.get("event") == "request_failed"]
    retrievals = [r for r in records if r.get("tool_name") == "retrieval" and r.get("tool_success") is not None]
    latencies = [r["latency_ms"] for r in responses if isinstance(r.get("latency_ms"), (int, float))]
    ttfts = [r["ttft_ms"] for r in responses if isinstance(r.get("ttft_ms"), (int, float))]
    costs: dict[str, float] = defaultdict(float)
    traffic: Counter[str] = Counter()
    for record in responses:
        costs[record["_minute"]] += float(record.get("cost_usd") or 0)
    for record in received:
        traffic[record["_minute"]] += 1
    quality = [r["quality_score"] for r in responses if isinstance(r.get("quality_score"), (int, float))]
    total = len(received)
    error_rate = len(failures) / total * 100 if total else None
    retrieval_success = sum(r["tool_success"] is True for r in retrievals) / len(retrievals) * 100 if retrievals else None
    good = sum((r.get("latency_ms") or 0) <= 3000 for r in responses)
    values = {
        "latency": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99), "ttft_p95": percentile(ttfts, 95)},
        "traffic": {"count": total, "rate_per_minute": round(total / config["time_range_minutes"], 2), "by_minute": dict(sorted(traffic.items()))},
        "errors": {"error_rate_pct": round(error_rate, 2) if error_rate is not None else None, "error_breakdown": dict(Counter(r.get("error_type", "unknown") for r in failures)), "retrieval_success_pct": round(retrieval_success, 2) if retrieval_success is not None else None},
        "cost": {"total": round(sum(costs.values()), 6), "by_minute": {key: round(value, 6) for key, value in sorted(costs.items())}},
        "tokens": {"input": sum(int(r.get("tokens_in") or 0) for r in responses), "output": sum(int(r.get("tokens_out") or 0) for r in responses)},
        "quality": {"mean": round(mean(quality), 3) if quality else None},
    }
    return {
        "title": config["title"],
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "time_range_minutes": config["time_range_minutes"],
        "refresh_seconds": config["refresh_seconds"],
        "slo": {"good": good, "total": total, "achieved_percent": round(good / total * 100, 2) if total else None, "target_percent": 99.5},
        "panels": [
            {"id": panel["id"], "title": panel["title"], "unit": panel["unit"], "threshold": panel["threshold"], "values": values[panel["id"]]}
            for panel in config["panels"]
        ],
    }


DASHBOARD_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Day 13 Monitoring Dashboard</title>
<style>
:root{font-family:Segoe UI,Arial,sans-serif;color:#e8edf7;background:#0b1220}body{margin:0;padding:28px;max-width:1500px;margin:auto}
header{display:flex;justify-content:space-between;align-items:end;gap:20px;border-bottom:1px solid #26344a;padding-bottom:20px}h1{font-size:28px;margin:0 0 6px}p{color:#aab8cf;margin:0}
.badge{padding:8px 12px;background:#18304b;border:1px solid #3b668f;border-radius:6px;color:#b9defb;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:24px}.card{background:#142238;border:1px solid #2b405d;border-radius:12px;padding:20px;min-height:220px}
h2{margin:0 0 6px;font-size:18px}.unit{font-size:12px;color:#9eb5ce;text-transform:uppercase;letter-spacing:.08em}.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:20px}
.metric{background:#0d1b2d;padding:12px;border-radius:8px}.metric strong{display:block;font-size:25px;color:#6ad7ca}.metric small{color:#afc0d4;font-size:12px}
.threshold{margin-top:15px;color:#ffcd86;font-size:13px}.chart{width:100%;height:70px;margin-top:14px;overflow:visible}
footer{margin-top:20px;color:#91a4bf;font-size:13px}@media(max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.grid{grid-template-columns:1fr}header{display:block}.badge{display:inline-block;margin-top:12px}}
</style></head><body>
<header><div><h1 id="title">Day 13 Monitoring &amp; LLMOps</h1><p id="range">Loading 60-minute window...</p></div><div class="badge" id="status">Refreshing every 30 seconds</div></header>
<main class="grid" id="panels"></main><footer id="slo"></footer>
<script>
const labels={latency:{p50:'P50 latency',p95:'P95 latency',p99:'P99 latency',ttft_p95:'TTFT P95'},traffic:{count:'Requests',rate_per_minute:'Requests/min'},errors:{error_rate_pct:'Error rate %',retrieval_success_pct:'Retrieval success %'},cost:{total:'Total USD'},tokens:{input:'Input tokens',output:'Output tokens'},quality:{mean:'Mean score'}};
function elem(tag,cls,value){const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)node.textContent=String(value);return node}
function fmt(value){return value===null||value===undefined?'No data':typeof value==='number'?Number.isInteger(value)?String(value):value.toFixed(3):String(value)}
function chart(series){const entries=Object.entries(series||{});if(!entries.length)return null;const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 300 70');svg.setAttribute('class','chart');const max=Math.max(...entries.map(item=>item[1]),1e-9);const width=Math.min(90,260/entries.length-8);entries.forEach(([minute,value],i)=>{const x=(i+.5)*300/entries.length-width/2;const height=value/max*42;const bar=document.createElementNS('http://www.w3.org/2000/svg','rect');bar.setAttribute('x',x);bar.setAttribute('y',48-height);bar.setAttribute('width',width);bar.setAttribute('height',height);bar.setAttribute('fill','#6ad7ca');bar.setAttribute('opacity','.8');svg.append(bar);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x',x+width/2);label.setAttribute('y',65);label.setAttribute('text-anchor','middle');label.setAttribute('fill','#9eb5ce');label.setAttribute('font-size','11');label.textContent=minute;svg.append(label)});return svg}
async function refresh(){try{const response=await fetch('/dashboard-data',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();document.getElementById('title').textContent=data.title;document.getElementById('range').textContent=`Last ${data.time_range_minutes} minutes · ${new Date(data.window_start).toLocaleString()} – ${new Date(data.window_end).toLocaleString()}`;document.getElementById('status').textContent=`Live · refresh ${data.refresh_seconds}s`;const grid=document.getElementById('panels');grid.replaceChildren();for(const panel of data.panels){const card=elem('section','card');card.append(elem('h2','',panel.title),elem('div','unit',panel.unit));const metrics=elem('div','metrics');for(const [key,label] of Object.entries(labels[panel.id])){const metric=elem('div','metric');metric.append(elem('strong','',fmt(panel.values[key])),elem('small','',label));metrics.append(metric)}card.append(metrics);const threshold=panel.threshold;card.append(elem('div','threshold',`Threshold: ${threshold.aggregation} ${threshold.operator==='lte'?'≤':'≥'} ${threshold.value} ${panel.unit}`));const line=chart(panel.values.by_minute);if(line)card.append(line);if(panel.id==='errors'){card.append(elem('p','',`Breakdown: ${JSON.stringify(panel.values.error_breakdown)}`))}grid.append(card)}document.getElementById('slo').textContent=`SLO: ${fmt(data.slo.achieved_percent)}% good requests (${data.slo.good}/${data.slo.total}) · target ${data.slo.target_percent}%`;}catch(error){document.getElementById('status').textContent='Dashboard error: '+error.message}}
refresh();setInterval(refresh,30000);
</script></body></html>"""
