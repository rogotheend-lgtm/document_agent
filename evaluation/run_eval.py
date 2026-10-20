import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
BASE_URL = "http://127.0.0.1:8200"


def post(client: httpx.Client, path: str, case: dict) -> tuple[dict, float]:
    started = time.perf_counter()
    response = client.post(
        f"{BASE_URL}{path}",
        json={
            "message": case["question"],
            "report_id": case["report_id"],
            "thread_id": f"eval-{case['id']}",
        },
    )
    latency = time.perf_counter() - started
    response.raise_for_status()
    return response.json(), latency


def run() -> None:
    cases = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    comparable = [case for case in cases if case["report_id"]]
    rows = []

    with httpx.Client(timeout=180) as client:
        for case in cases:
            improved, improved_latency = post(client, "/api/chat", case)
            row = {
                **case,
                "improved_route": improved["route"],
                "improved_sources": len(improved.get("sources", [])),
                "evidence_status": improved.get("evidence_status"),
                "evidence_confidence": improved.get("evidence_confidence"),
                "improved_latency_seconds": round(improved_latency, 3),
                "route_correct": improved["route"] == case["expected_route"],
                "source_correct": bool(improved.get("sources")) == case["should_have_sources"],
            }
            if case in comparable:
                baseline, baseline_latency = post(client, "/api/chat/baseline", case)
                row.update({
                    "baseline_latency_seconds": round(baseline_latency, 3),
                    "baseline_answer": baseline["answer"],
                })
            rows.append(row)

    improved_latencies = [row["improved_latency_seconds"] for row in rows]
    baseline_latencies = [row["baseline_latency_seconds"] for row in rows if "baseline_latency_seconds" in row]
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(rows),
        "route_accuracy": round(sum(row["route_correct"] for row in rows) / len(rows), 3),
        "source_accuracy": round(sum(row["source_correct"] for row in rows) / len(rows), 3),
        "improved_average_latency_seconds": round(statistics.mean(improved_latencies), 3),
        "baseline_average_latency_seconds": round(statistics.mean(baseline_latencies), 3),
    }
    output = {"summary": summary, "cases": rows}
    (ROOT / "results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
