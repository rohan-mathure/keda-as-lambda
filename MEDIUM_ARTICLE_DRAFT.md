# KEDA-as-Lambda: Building Serverless Workloads on Kubernetes

> **Status**: Draft for Medium publication
> **Repo**: [keda-as-lambda](https://github.com/rohanmathure/keda-as-lambda)
> **Author**: Rohan Mathure
> **Reading time**: ~12 min

## Introduction

AWS Lambda has dominated the serverless landscape for years, offering pay-per-invocation pricing and zero-ops deployment. But what if your team already runs Kubernetes? What if you need runtimes Lambda doesn't support, or want to escape vendor lock-in?

**KEDA** (Kubernetes Event-Driven Autoscaling) offers a compelling alternative: bring serverless semantics to your Kubernetes cluster.

In this article, we'll explore what KEDA is, why you might choose it over Lambda, how to build Lambda-like workloads on it, and what our proof-of-concept revealed about governance, cost, and operational trade-offs.

---

## Part 1: The Problem

### The Lambda Constraint

AWS Lambda is great for simple, bursty workloads:
- **No ops**: AWS handles infrastructure, scaling, security patches
- **Pay per invocation**: $0.20 per 1M invocations + $0.0000167 per GB-second
- **Fast cold start**: ~100–500ms
- **Built-in triggers**: S3, SNS, SQS, API Gateway, EventBridge, DynamoDB, etc.

But Lambda has hard limits:
- **15-minute execution timeout** (no long-running jobs)
- **10 GB memory maximum** (no memory-intensive workloads)
- **10 GB `/tmp` scratch space** (limited for batch processing)
- **Managed runtimes only** (Python, Node, Go, Java, C#, Ruby; no Rust, Zig, or custom versions)
- **Vendor lock-in**: Lambda-specific APIs, CloudWatch-only logging

### The Kubernetes Reality

If you're already running Kubernetes (EKS, GKE, AKS, or self-managed), you have:
- ✅ Unified governance (RBAC, OPA policies, audit logs)
- ✅ Existing observability stack (Prometheus, Grafana, ELK)
- ✅ Cost-efficiency measures (spot instances, bin-packing, resource sharing)
- ✅ But no native way to scale jobs based on event queues

**KEDA bridges this gap.**

---

## Part 2: What is KEDA?

### The Core Idea

**KEDA** = Kubernetes Event-Driven Autoscaling

KEDA extends Kubernetes with two new resource types:
1. **ScaledObject**: Auto-scales a traditional Deployment/StatefulSet based on external event sources
2. **ScaledJob**: Auto-creates Kubernetes Jobs based on event queue depth (this is our focus)

### ScaledJob vs. Deployment

| Aspect | ScaledJob | Deployment |
|--------|-----------|-----------|
| **Pod lifecycle** | Ephemeral (created per trigger) | Persistent (always running) |
| **Semantics** | One pod per N events (Lambda-like) | Keep N replicas running |
| **Cleanup** | Automatic (pod deleted after job) | Manual (replica remains) |
| **Use case** | Batch jobs, event processing | Long-running services |

For Lambda-like workloads, **ScaledJob is the right choice**.

### How It Works

```
Event Source (SQS, Kafka, etc.)
          ↓
    KEDA Scaler
          ↓
    Monitor queue depth
          ↓
    Calculate desired job replicas
          ↓
    Kubernetes Job Controller
          ↓
    Spawn pods (one per job)
          ↓
    Container runs handler
          ↓
    Pod exits, Job completes, KEDA deletes pod
```

---

## Part 3: Building a KEDA Workload

### Project Structure

Our POC uses this structure:

```
keda-as-lambda/
├── keda/
│   ├── scaled-job-sqs.yaml      # SQS → Jobs
│   ├── scaled-job-sns.yaml      # SNS → SQS → Jobs
│   ├── scaled-job-cron.yaml     # Cron → Jobs
│   └── values.yaml              # KEDA Helm config
├── workload/
│   ├── Dockerfile               # Python 3.12 handler
│   ├── handler.py               # Lambda-style entry point
│   └── requirements.txt          # Dependencies (boto3)
├── load-generator/
│   ├── send_messages.py         # Sends test events
│   └── requirements.txt          # boto3
└── cluster/
    ├── k3d-config.yaml          # Local k3s cluster
    └── localstack/              # AWS mock (SQS/SNS)
```

### The Handler

Our `workload/handler.py` mimics a Lambda handler:

```python
def lambda_handler(event, context):
    """Lambda-style handler; receives event dict."""
    try:
        logger.info(f"Processing: {event}")
        # Do work here
        time.sleep(1.5)  # Simulate work
        return {"statusCode": 200, "message": "success"}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"statusCode": 500, "error": str(e)}
```

When deployed as a KEDA job, the message body is passed via environment variables, and the handler processes it exactly as if it were a Lambda invocation.

### The ScaledJob Definition

Here's a simplified SQS-triggered ScaledJob:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: demo-sqs-job
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: handler
          image: keda-demo:latest
          env:
          - name: AWS_ENDPOINT_URL
            value: "http://localstack:4566"
  pollingInterval: 5
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: "http://localstack:4566/queue/demo-queue"
      awsRegion: "us-east-1"
    authenticationRef:
      name: aws-credentials
```

**Key parts**:
- `jobTargetRef`: The Kubernetes Job template to spawn
- `pollingInterval`: How often to check queue depth (seconds)
- `minReplicaCount`: Min jobs to keep running (0 = true serverless)
- `maxReplicaCount`: Max concurrent jobs (10)
- `triggers`: External event sources (SQS, SNS, Kafka, HTTP, Cron, etc.)

### Trigger Authentication

KEDA needs AWS credentials for SQS. Store them in a K8s Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "your-key-id"
  AWS_SECRET_ACCESS_KEY: "your-secret"
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: aws-credentials-trigger
spec:
  secretTargetRef:
  - parameter: awsAccessKeyId
    name: aws-credentials
    key: AWS_ACCESS_KEY_ID
  - parameter: awsSecretAccessKey
    name: aws-credentials
    key: AWS_SECRET_ACCESS_KEY
```

---

## Part 4: Running the POC

### Prerequisites

```bash
# Install tooling
brew install k3d helm kubectl
pip install boto3 awscli-local

# Clone the repo
git clone https://github.com/rohanmathure/keda-as-lambda.git
cd keda-as-lambda
```

### Quick Start (Cron Demo)

For a dependency-free demo, use the Cron trigger:

```bash
# 1. Create cluster
make cluster-up

# 2. Install KEDA
make keda-up

# 3. Deploy cron-triggered job
kubectl apply -f keda/scaled-job-cron.yaml -n demo

# 4. Watch jobs spawn every hour
kubectl get jobs -n demo -w
```

### Full Demo (SQS + SNS)

For a realistic test with message queues:

```bash
make cluster-up
make localstack-up      # Runs LocalStack (SQS/SNS mock)
make init-aws           # Creates queues & topics
make keda-up            # Installs KEDA
make build              # Builds handler image
make demo-sqs N=20      # Sends 20 messages → 20 jobs spawn
make demo-sns N=20      # SNS → SQS subscription → 20 jobs
```

---

## Part 5: Configuration Breakdown

### KEDA Helm Values (`keda/values.yaml`)

```yaml
replicaCount: 1
image:
  repository: ghcr.io/kedacore/keda-operator
  tag: ""  # Uses default
resources:
  limits:
    cpu: 1000m
    memory: 1000Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

This is minimal; KEDA's operator runs in your cluster and watches for ScaledJobs.

### ScaledJob Metadata

| Field | Purpose | Example |
|-------|---------|---------|
| `pollingInterval` | Check queue every N seconds | `5` |
| `minReplicaCount` | Minimum jobs running | `0` (true serverless) |
| `maxReplicaCount` | Maximum concurrent jobs | `10` |
| `jobTargetRef` | Kubernetes Job to spawn | Pod template + containers |
| `triggers` | Event sources to watch | SQS, SNS, HTTP, Cron, Kafka |

### Trigger Types

KEDA supports 50+ trigger types:

| Trigger | Use | Config |
|---------|-----|--------|
| `aws-sqs-queue` | Process SQS messages | queueURL, region, credentials |
| `aws-sns` | N/A (route to SQS) | SNS → SQS subscription |
| `kafka` | Kafka topics | brokers, topic, consumer group |
| `cron` | Schedule jobs | cron expression (e.g., `0 * * * *`) |
| `http` | HTTP polling | endpoint, method |
| `rabbitmq` | RabbitMQ queues | connection string, queue name |
| `nats` | NATS subjects | nats:// URL, subject |

---

## Part 6: Analysis & Findings

### Governance Advantage

KEDA jobs are native Kubernetes workloads:
- ✅ Subject to the same RBAC policies
- ✅ Visible in `kubectl get pods`
- ✅ Integrated with your observability stack (Prometheus, Grafana)
- ✅ Auditable via Kubernetes audit logs
- ✅ Can use the same namespaces, quotas, and network policies

Lambda, by contrast, is managed by AWS:
- ❌ Separate IAM policies
- ❌ Separate CloudWatch logs
- ❌ No native Kubernetes integration
- ❌ Limited visibility into execution environment

### Cold Start Trade-off

| Metric | Lambda | KEDA |
|--------|--------|------|
| **Cold start** | ~100–500ms | ~1–3s (pod scheduling + container init) |
| **Warm start** | <10ms | <100ms |
| **Scalability** | Automatic (up to 10K concurrent) | Limited by cluster size |

**Verdict**: Lambda wins on latency. KEDA acceptable for batch/queue jobs where 1–3s startup is fine.

### Cost Comparison

We modeled three scenarios:

#### Scenario 1: Small Workload (100K–2M invocations/month)
- **Lambda**: Free tier covers 1M invocations/month + 400K GB-seconds
- **KEDA (1 spot node)**: ~$9/month fixed
- **Winner**: Lambda (free tier)

#### Scenario 2: Medium Workload (1M–50M invocations/month)
- **Lambda (512MB, 500ms avg)**: $15–$211/month
- **KEDA (3 spot nodes + EKS)**: ~$100/month fixed
- **Break-even**: ~25M invocations/month
- **Winner**: KEDA at high volumes

#### Scenario 3: High-Volume Workload (10M–500M invocations/month)
- **Lambda (1GB, 1s avg)**: $162–$8,400/month
- **KEDA (10 spot nodes + EKS)**: ~$164/month fixed
- **Savings at 100M**: 90% cheaper with KEDA
- **Winner**: KEDA decisively

**Key insight**: KEDA's fixed infrastructure cost breaks even around 500K–1M invocations/month. Above that, it's significantly cheaper. Spot instances amplify savings (70% discount on compute).

### Runtime & Flexibility

KEDA removes Lambda's hard limits:

| Dimension | Lambda | KEDA |
|-----------|--------|------|
| **Timeout** | 15 min (hard limit) | Configurable |
| **Memory** | 10 GB max | Cluster capacity |
| **Scratch space** | 10 GB `/tmp` | Node disk |
| **Runtimes** | AWS-managed only | Any container image |
| **Dependencies** | Deployment package ≤ 250 MB | Any size |

For ML inference, video processing, or long-running batch jobs, KEDA is superior.

### Operational Complexity

| Task | Lambda | KEDA |
|------|--------|------|
| **Setup** | 5 min (console clicks) | 15–30 min (cluster + KEDA + handlers) |
| **Day 2 Ops** | Managed by AWS | You own cluster, upgrades, security patches |
| **Debugging** | CloudWatch Logs + X-Ray | kubectl logs, Kubernetes dashboard |
| **Scaling** | Automatic | Auto-scales pods; manual cluster scaling |

Lambda is simpler. KEDA requires Kubernetes expertise.

---

## Part 7: When to Choose KEDA over Lambda

### Choose KEDA if:
- ✅ You already run Kubernetes (even just for other workloads)
- ✅ Workloads need custom runtimes (Rust, Zig, etc.) or old runtime versions
- ✅ You need >15 min execution time or >10 GB memory
- ✅ Volume is predictable or high (>500K invocations/month)
- ✅ Cost optimization is critical
- ✅ Unified governance matters (same RBAC, audit logs, observability)

### Choose Lambda if:
- ✅ Minimal operational overhead is priority
- ✅ Workloads are truly bursty (<100K invocations/month)
- ✅ <1s cold start is essential (HTTP APIs, webhooks)
- ✅ You need comprehensive trigger coverage (S3, DynamoDB, EventBridge)
- ✅ AWS is your primary platform

### Hybrid Approach:
- Lambda for bursty, low-latency triggers (API calls, webhooks)
- KEDA for batch jobs, queue processing, predictable workloads
- Bridge gaps with EventBridge → SQS → KEDA

---

## Part 8: Next Steps

### Extend the POC

The repo includes a full working example. Next steps:
1. **Add more triggers**: Kafka, HTTP, Postgres, RabbitMQ
2. **Implement keep-alive pools**: Pre-warm pods to reduce cold start
3. **Add cost tracking**: Export metrics to cost analyzer
4. **Test at scale**: Run 1K+ concurrent jobs, measure throughput
5. **Integrate observability**: Send metrics to Prometheus/Grafana

### Production Deployment

- Replace LocalStack with real AWS (SQS, SNS, Kinesis)
- Use EKS instead of k3s; enable cluster auto-scaling
- Add security: TLS, RBAC, network policies
- Set resource quotas per namespace
- Enable KEDA autoscaling per trigger type

---

## Conclusion

KEDA brings serverless semantics to Kubernetes without Lambda's constraints. For teams with existing K8s infrastructure and predictable workloads, it's a powerful alternative that saves cost, improves governance, and removes runtime limits.

Lambda remains superior for simplicity and low-latency use cases. The optimal choice depends on your workload profile, team expertise, and existing infrastructure.

**Try it**: Clone the [keda-as-lambda](https://github.com/rohanmathure/keda-as-lambda) repo and run `make demo-sqs N=10`. You'll see KEDA spawn 10 jobs in seconds.

---

## References

- KEDA Docs: https://keda.sh/
- k3d (k3s in Docker): https://k3d.io/
- LocalStack (AWS mock): https://localstack.cloud/
- AWS Lambda Pricing: https://aws.amazon.com/lambda/pricing/
- KEDA Scalers: https://keda.sh/docs/latest/scalers/

---

## Appendix: Cost Model Code

See `analysis/cost_model.py` for the full breakdown:
- Lambda pricing: invocation fee + compute (GB-seconds)
- KEDA pricing: fixed node cost + optional EKS management fee
- Spot discount modeling for realistic on-prem-like costs

Run: `python analysis/cost_model.py`

---

**Questions?** Open an issue on [GitHub](https://github.com/rohanmathure/keda-as-lambda/issues) or reach out on [Twitter](https://twitter.com/rohanmathure).
