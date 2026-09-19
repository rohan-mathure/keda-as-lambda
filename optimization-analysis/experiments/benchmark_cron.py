#!/usr/bin/env python3
"""
Baseline measurement using Cron trigger (no SQS required).
Measures cold-start latency from job creation to handler execution.
"""

import json
import time
import subprocess
import statistics
from datetime import datetime
from typing import Dict, List, Optional

def run_job() -> Optional[Dict]:
    """Deploy cron scaledjob, wait for job, measure execution time."""

    # Apply cron ScaledJob
    print("  Applying cron ScaledJob...")
    result = subprocess.run(
        ["kubectl", "apply", "-f", "/Users/rohanmathure/Projects/experiments/keda-as-lambda/keda/scaled-job-cron.yaml", "-n", "demo"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        print(f"    Error: {result.stderr}")
        return None

    # Wait for job to be created
    time.sleep(2)

    job_created = None
    start_time = time.time()

    while time.time() - start_time < 60:
        result = subprocess.run(
            ["kubectl", "get", "jobs", "-n", "demo", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            jobs = json.loads(result.stdout)
            if jobs.get("items"):
                job = jobs["items"][0]
                if not job_created:
                    job_created = time.time()
                    job_name = job["metadata"]["name"]
                    print(f"  ✓ Job created: {job_name}")

                # Check if job completed
                if job["status"].get("succeeded", 0) > 0:
                    job_completed = time.time()
                    print(f"  ✓ Job completed")

                    # Get pod logs to find handler start time
                    pod_result = subprocess.run(
                        ["kubectl", "logs", "-n", "demo", "-l", f"job-name={job_name}", "--timestamps=true"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if pod_result.returncode == 0 and pod_result.stdout:
                        # Extract first log line timestamp
                        first_log = pod_result.stdout.split('\n')[0]
                        print(f"  First log: {first_log[:80]}...")

                    return {
                        "job_created": job_created,
                        "job_completed": job_completed,
                        "delta": job_completed - job_created if job_completed and job_created else None
                    }

        time.sleep(1)

    print("  ✗ Job did not complete within 60s")
    return None

def run_baseline(trials: int = 5) -> Dict:
    """Run N cron job trials."""

    print(f"\n🔬 Cron-based Baseline Measurement: {trials} trials")
    print("   (No SQS required, measures job creation to completion)\n")

    measurements = []

    for i in range(trials):
        print(f"Trial {i+1}/{trials}:")

        # Clean up previous jobs
        subprocess.run(
            ["kubectl", "delete", "jobs", "--all", "-n", "demo"],
            capture_output=True,
            timeout=10
        )

        time.sleep(1)

        # Run job
        result = run_job()
        if result:
            measurements.append(result)
            delta = result.get("delta")
            if delta:
                print(f"  Latency: {delta:.2f}s\n")

        time.sleep(2)

    if not measurements:
        print("\n❌ No successful measurements!")
        return {}

    deltas = [m["delta"] for m in measurements if m.get("delta")]

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "method": "cron_trigger",
        "note": "Measures job creation to job completion (not handler execution start)",
        "trials": len(measurements),
        "measurements": measurements,
        "stats": {
            "job_to_completion": {
                "count": len(deltas),
                "p50": statistics.median(deltas) if deltas else None,
                "p95": percentile(deltas, 95) if deltas else None,
                "p99": percentile(deltas, 99) if deltas else None,
                "min": min(deltas) if deltas else None,
                "max": max(deltas) if deltas else None,
                "mean": statistics.mean(deltas) if deltas else None,
            }
        }
    }

    return results

def percentile(data: List[float], p: float) -> float:
    if not data:
        return None
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * (p / 100))
    return sorted_data[idx]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5, help="Number of trials")
    parser.add_argument("--output", default="exp1_baseline_cron.json", help="Output file")
    args = parser.parse_args()

    results = run_baseline(trials=args.trials)

    if results:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"✅ Results saved to {args.output}")
        print(f"\n📊 Summary (job creation → completion):")
        print(f"   p50: {results['stats']['job_to_completion']['p50']:.2f}s")
        print(f"   p95: {results['stats']['job_to_completion']['p95']:.2f}s")
        print(f"   mean: {results['stats']['job_to_completion']['mean']:.2f}s")
    else:
        print("\n❌ Benchmark failed!")
