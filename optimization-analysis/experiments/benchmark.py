#!/usr/bin/env python3
"""
Timing harness for KEDA cold-start measurement.
Sends messages, tracks job creation and execution, produces latency stats.
"""

import json
import time
import uuid
import subprocess
import statistics
import sys
from datetime import datetime
from typing import Dict, List, Optional

class LatencyMeasurement:
    def __init__(self):
        self.sent_at = None
        self.job_created_at = None
        self.pod_running_at = None
        self.handler_start_at = None

    def to_dict(self):
        return {
            "sent_at": self.sent_at,
            "job_created_at": self.job_created_at,
            "pod_running_at": self.pod_running_at,
            "handler_start_at": self.handler_start_at,
            "deltas": {
                "send_to_job_created": self.job_created_at - self.sent_at if self.job_created_at else None,
                "send_to_pod_running": self.pod_running_at - self.sent_at if self.pod_running_at else None,
                "send_to_handler_start": self.handler_start_at - self.sent_at if self.handler_start_at else None,
                "job_created_to_pod_running": self.pod_running_at - self.job_created_at if self.pod_running_at and self.job_created_at else None,
                "pod_running_to_handler_start": self.handler_start_at - self.pod_running_at if self.handler_start_at and self.pod_running_at else None,
            }
        }

def send_message(queue_endpoint: str, queue_name: str, run_id: str, sent_at: float) -> Optional[str]:
    """Send a message with timing info to SQS queue."""
    try:
        message_body = json.dumps({
            "run_id": run_id,
            "sent_at": sent_at,
            "test": "baseline"
        })

        # Use AWS CLI with LocalStack endpoint
        result = subprocess.run(
            [
                "awslocal",
                "--endpoint-url", queue_endpoint,
                "sqs", "send-message",
                "--queue-url", f"{queue_endpoint}/000000000000/{queue_name}",
                "--message-body", message_body,
                "--region", "us-east-1"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = json.loads(result.stdout)
            print(f"  ✓ Message sent (run_id={run_id})")
            return run_id
        else:
            print(f"  ✗ Failed to send message: {result.stderr}")
            return None
    except Exception as e:
        print(f"  ✗ Error sending message: {e}")
        return None

def wait_for_job_created(run_id: str, namespace: str = "demo", timeout: int = 60) -> Optional[float]:
    """Wait for KEDA to create a Job, return timestamp when detected."""
    start_wait = time.time()

    while time.time() - start_wait < timeout:
        try:
            result = subprocess.run(
                ["kubectl", "get", "jobs", "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                jobs = json.loads(result.stdout)
                # Find job with our label
                for job in jobs.get("items", []):
                    labels = job.get("metadata", {}).get("labels", {})
                    if labels.get("run-id") == run_id:
                        return time.time()
        except Exception as e:
            pass

        time.sleep(1)

    return None

def wait_for_pod_running(job_name: str, namespace: str = "demo", timeout: int = 60) -> Optional[float]:
    """Wait for job's pod to reach Running state."""
    start_wait = time.time()

    while time.time() - start_wait < timeout:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", namespace, "-l", f"job-name={job_name}", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                pods = json.loads(result.stdout)
                for pod in pods.get("items", []):
                    phase = pod.get("status", {}).get("phase")
                    if phase == "Running":
                        return time.time()
        except Exception as e:
            pass

        time.sleep(0.5)

    return None

def wait_for_handler_start(run_id: str, namespace: str = "demo", timeout: int = 60) -> Optional[float]:
    """Wait for handler to log 'Received event', then extract sent_at from message."""
    start_wait = time.time()

    while time.time() - start_wait < timeout:
        try:
            result = subprocess.run(
                ["kubectl", "logs", "-n", namespace, "-l", f"run-id={run_id}", "--tail=20"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and "Received event" in result.stdout:
                return time.time()
        except Exception as e:
            pass

        time.sleep(0.5)

    return None

def run_benchmark(
    trials: int = 20,
    queue_endpoint: str = "http://localhost:4566",
    queue_name: str = "demo-queue",
    namespace: str = "demo"
) -> Dict:
    """Run N trials of send-to-execution timing."""

    print(f"\n🔬 Baseline Measurement: {trials} trials")
    print(f"   Endpoint: {queue_endpoint}")
    print(f"   Queue: {queue_name}")
    print(f"   Namespace: {namespace}")

    measurements: List[LatencyMeasurement] = []

    for i in range(trials):
        print(f"\nTrial {i+1}/{trials}:")
        m = LatencyMeasurement()
        run_id = str(uuid.uuid4())[:8]

        # 1. Send message
        m.sent_at = time.time()
        if not send_message(queue_endpoint, queue_name, run_id, m.sent_at):
            print(f"  ⊘ Skipping trial (send failed)")
            continue

        # 2. Wait for Job created
        m.job_created_at = wait_for_job_created(run_id, namespace, timeout=60)
        if not m.job_created_at:
            print(f"  ⊘ Skipping trial (job not created)")
            continue
        print(f"  ✓ Job created in {m.job_created_at - m.sent_at:.2f}s")

        # 3. Wait for Pod running
        # (Job name = namespace + run_id prefix, but K8s truncates; search by run-id label instead)
        m.pod_running_at = wait_for_pod_running("", namespace, timeout=30)
        if m.pod_running_at:
            print(f"  ✓ Pod running in {m.pod_running_at - m.sent_at:.2f}s (since send)")

        # 4. Wait for handler to log receipt
        m.handler_start_at = wait_for_handler_start(run_id, namespace, timeout=30)
        if m.handler_start_at:
            print(f"  ✓ Handler started in {m.handler_start_at - m.sent_at:.2f}s (since send)")

        measurements.append(m)
        time.sleep(1)  # Pause between trials

    # Compute stats
    if not measurements:
        print("\n❌ No successful measurements!")
        return {}

    send_to_handler = [m.to_dict()["deltas"]["send_to_handler_start"] for m in measurements if m.handler_start_at]
    send_to_job = [m.to_dict()["deltas"]["send_to_job_created"] for m in measurements if m.job_created_at]

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "trials": len(measurements),
        "measurements": [m.to_dict() for m in measurements],
        "stats": {
            "send_to_handler_start": {
                "count": len(send_to_handler),
                "p50": statistics.median(send_to_handler) if send_to_handler else None,
                "p95": percentile(send_to_handler, 95) if send_to_handler else None,
                "p99": percentile(send_to_handler, 99) if send_to_handler else None,
                "min": min(send_to_handler) if send_to_handler else None,
                "max": max(send_to_handler) if send_to_handler else None,
                "mean": statistics.mean(send_to_handler) if send_to_handler else None,
            },
            "send_to_job_created": {
                "count": len(send_to_job),
                "p50": statistics.median(send_to_job) if send_to_job else None,
                "p95": percentile(send_to_job, 95) if send_to_job else None,
                "p99": percentile(send_to_job, 99) if send_to_job else None,
                "min": min(send_to_job) if send_to_job else None,
                "max": max(send_to_job) if send_to_job else None,
            }
        }
    }

    return results

def percentile(data: List[float], p: float) -> float:
    """Compute percentile."""
    if not data:
        return None
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * (p / 100))
    return sorted_data[idx]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=20, help="Number of trials")
    parser.add_argument("--endpoint", default="http://localhost:4566", help="LocalStack endpoint")
    parser.add_argument("--queue", default="demo-queue", help="SQS queue name")
    parser.add_argument("--namespace", default="demo", help="K8s namespace")
    parser.add_argument("--output", default=None, help="Output JSON file (default: exp1_baseline.json)")
    args = parser.parse_args()

    results = run_benchmark(
        trials=args.trials,
        queue_endpoint=args.endpoint,
        queue_name=args.queue,
        namespace=args.namespace
    )

    output_file = args.output or "exp1_baseline.json"
    if results:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results written to {output_file}")
        print(f"\n📊 Summary:")
        print(f"   p50 end-to-end: {results['stats']['send_to_handler_start']['p50']:.2f}s")
        print(f"   p95 end-to-end: {results['stats']['send_to_handler_start']['p95']:.2f}s")
        print(f"   p99 end-to-end: {results['stats']['send_to_handler_start']['p99']:.2f}s")
    else:
        print("\n❌ Benchmark failed!")
        sys.exit(1)
