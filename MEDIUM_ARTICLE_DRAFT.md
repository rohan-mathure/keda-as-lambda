# KEDA-as-Lambda: Building Serverless Workloads on Kubernetes

> **Status**: Draft for Medium publication
> **Repo**: [rohan-mathure/keda-as-lambda](https://github.com/rohan-mathure/keda-as-lambda)
> **Author**: Rohan Mathure
> **Reading time**: ~12 min

## Introduction

AWS Lambda has dominated the serverless landscape for years, offering pay-per-invocation pricing and zero-ops deployment. But what if your team already runs Kubernetes? What if you need runtimes Lambda doesn't support, or want to escape vendor lock-in?

**KEDA** (Kubernetes Event-Driven Autoscaling) offers a compelling alternative: bring serverless semantics to your Kubernetes cluster.

In this article, I'll explore what KEDA is, why you might choose it over Lambda, how to build Lambda-like workloads on it, and what my proof-of-concept revealed about governance, cost, and operational trade-offs.

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

I'll start with the basics.

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

For Lambda-like workloads, I use **ScaledJob**.

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

My POC uses this structure:

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

My `workload/handler.py` mimics a Lambda handler:

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

KEDA needs credentials to access external event sources (SQS, SNS, Kafka, etc.). **TriggerAuthentication** is a Kubernetes resource that securely stores and injects these credentials into scalers.

#### Why Separate Authentication?

Rather than embedding secrets in ScaledJob definitions, KEDA uses a dedicated `TriggerAuthentication` resource:
- **Reusability**: One auth resource, multiple scalers
- **Security**: Secrets stored in K8s Secret; not in ScaledJob spec
- **Flexibility**: Swap credentials without modifying ScaledJob
- **Auditing**: Track credential usage via K8s audit logs

#### How It Works

```
ScaledJob
  └── triggers[0].authenticationRef
        └── name: "aws-credentials-trigger"
              └── TriggerAuthentication: "aws-credentials-trigger"
                    └── secretTargetRef
                          └── Secret: "aws-credentials"
                                └── AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

#### Minimal Example

1. **Create a K8s Secret** (stores actual credentials):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "your-key-id"
  AWS_SECRET_ACCESS_KEY: "your-secret"
```

2. **Create a TriggerAuthentication** (maps Secret fields to scaler parameters):

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: aws-credentials-trigger
spec:
  secretTargetRef:
  - parameter: awsAccessKeyId          # Scaler expects this param
    name: aws-credentials               # K8s Secret name
    key: AWS_ACCESS_KEY_ID              # Secret key
  - parameter: awsSecretAccessKey
    name: aws-credentials
    key: AWS_SECRET_ACCESS_KEY
```

3. **Reference in ScaledJob**:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: demo-sqs-job
spec:
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: "https://sqs.us-east-1.amazonaws.com/123456789/my-queue"
      awsRegion: "us-east-1"
    authenticationRef:                  # ← Link to TriggerAuthentication
      name: aws-credentials-trigger
```

#### Authentication Methods

KEDA supports multiple auth methods:

| Method | Use | Example |
|--------|-----|---------|
| `secretTargetRef` | K8s Secret fields | AWS IAM keys, API tokens |
| `env` | Pod environment | `$AWS_ACCESS_KEY_ID` |
| `hashiCorpVault` | HashiCorp Vault | Production secrets management |
| `azureKeyVault` | Azure Key Vault | For AKS clusters |
| `awsSecretsManager` | AWS Secrets Manager | Fetch from AWS, not K8s |
| `gcp` | GCP Service Accounts | For GKE clusters |

For SQS/SNS in my POC, **secretTargetRef** (K8s Secret) is simplest.

---

## Part 4: Running the POC

### Prerequisites

```bash
# Install tooling
brew install k3d helm kubectl
pip install boto3 awscli-local

# Clone the repo
git clone git@github.com:rohan-mathure/keda-as-lambda.git
cd keda-as-lambda
```

### Quick Start (Cron Demo)

For a dependency-free demo, I use the Cron trigger:

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

For a realistic test with message queues, I run:

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

## Part 4.5: Deep Dive - SQS & SNS Trigger Mechanisms

### SQS Trigger: How KEDA Scales Based on Queue Depth

The SQS scaler is KEDA's most common trigger. Here's how it works end-to-end:

#### 1. Polling Loop (Every 5 seconds by default)

```
KEDA Operator (running in keda namespace)
  ├─ Every pollingInterval seconds (e.g., 5s):
  │   ├─ Retrieve TriggerAuthentication → extract AWS credentials
  │   ├─ Call SQS API: GetQueueAttributes(QueueURL, "ApproximateNumberOfMessages")
  │   ├─ Get queue depth (e.g., 20 messages)
  │   ├─ Calculate desired job replicas: depth / batchSize
  │   │   (e.g., 20 messages / 1 msg per job = 20 jobs)
  │   ├─ Compare to current job count
  │   ├─ If desired > current: Create new Jobs
  │   └─ If desired < current: Delete excess Jobs
  └─ Repeat
```

#### 2. Concrete Example

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: sqs-processor
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: handler
          image: myapp:latest
          env:
          - name: SQS_QUEUE_URL
            value: "https://sqs.us-east-1.amazonaws.com/123456789/myqueue"
  
  pollingInterval: 5              # Check queue depth every 5 seconds
  minReplicaCount: 0              # Minimum jobs (0 = true serverless)
  maxReplicaCount: 20             # Maximum concurrent jobs
  
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: "https://sqs.us-east-1.amazonaws.com/123456789/myqueue"
      awsRegion: "us-east-1"
      batchSize: "1"              # One message per job
      messageDelay: "0"           # Ignore delay attributes
      visibilityTimeout: "300"    # 5-min timeout (must match handler timeout)
      scalingModulus: "1"         # Scale 1:1 with queue depth
      awsEndpoint: ""             # Use AWS; for LocalStack: "http://localstack:4566"
      identityOwner: "operator"   # Use KEDA pod's IAM role (or "workload" for job's role)
    authenticationRef:
      name: aws-credentials
```

#### 3. Message Flow & Visibility Timeout

**Important**: When a job receives a message, SQS marks it as "in-flight" (invisible to other consumers) for `visibilityTimeout` seconds.

```
T=0s: Message arrives in queue
      Queue depth: 1
      KEDA detects depth=1 → Creates Job #1

T=1s: Job #1 starts
      SQS hides message (visibility timeout = 300s)
      Queue visible depth: 0
      KEDA sees depth=0 → No new jobs

T=120s: Job #1 completes
        Job deletes message from SQS
        Message gone permanently

T=301s: (If Job #1 crashes without deleting)
        Visibility timeout expires
        Message reappears in queue
        KEDA may recreate job
```

**Best practice**: `visibilityTimeout` ≥ job execution time + buffer.

#### 4. Metadata Breakdown

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `queueURL` | Full SQS queue URL | `https://sqs.us-east-1.amazonaws.com/123456789/myqueue` |
| `awsRegion` | AWS region | `us-east-1` |
| `batchSize` | Messages per job (default 5) | `1` (one message per job = Lambda-like) |
| `messageDelay` | Ignore delay on messages (0=no, 1=yes) | `0` |
| `visibilityTimeout` | How long to hide message after receive | `300` (seconds) |
| `scalingModulus` | Scale factor (1 = 1:1 with depth) | `1` |
| `awsEndpoint` | Custom endpoint (LocalStack, etc.) | `http://localstack:4566` |
| `identityOwner` | Use operator or workload IAM role | `operator` or `workload` |

#### 5. Real SQS Scaler Behavior

```python
# Pseudocode inside KEDA's SQS scaler
def get_queue_depth():
    resp = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['ApproximateNumberOfMessages']
    )
    return int(resp['Attributes']['ApproximateNumberOfMessages'])

def calculate_desired_replicas():
    depth = get_queue_depth()
    batch_size = config['batchSize']  # e.g., 1
    desired = max(minReplicas, min(depth // batch_size, maxReplicas))
    return desired

# Every pollingInterval:
desired = calculate_desired_replicas()
current = count_running_jobs()
if desired > current:
    create_jobs(desired - current)
elif desired < current:
    delete_jobs(current - desired)
```

---

### SNS → SQS → KEDA Trigger Chain

SNS (Simple Notification Service) doesn't have native KEDA scaler. Instead, use the **SNS → SQS subscription** pattern:

#### Pattern Flow

```
SNS Topic (demo-topic)
  ├─ Publish event
  │   └─ Event sent to all subscribers
  └─ Subscriber: SQS Queue (demo-sns-queue)
        └─ Message lands in queue
              └─ KEDA SQS scaler detects it
                    └─ Spawns job
```

#### Setup

1. **Create SNS topic and SQS queue** (same AWS account/region):

```bash
aws sns create-topic --name demo-topic --region us-east-1
aws sqs create-queue --queue-name demo-sns-queue --region us-east-1
```

2. **Subscribe queue to topic**:

```bash
TOPIC_ARN="arn:aws:sns:us-east-1:123456789:demo-topic"
QUEUE_ARN="arn:aws:sqs:us-east-1:123456789:demo-sns-queue"
QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789/demo-sns-queue"

aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol sqs \
  --notification-endpoint $QUEUE_ARN \
  --region us-east-1

# Allow SNS to write to SQS (trust policy)
aws sqs set-queue-attributes \
  --queue-url $QUEUE_URL \
  --attributes file://policy.json
```

3. **Use SQS ScaledJob** (as before):

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: sns-processor
spec:
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: "https://sqs.us-east-1.amazonaws.com/123456789/demo-sns-queue"
      awsRegion: "us-east-1"
      batchSize: "1"
    # ... rest same as SQS example
```

4. **Publish to SNS**:

```bash
aws sns publish \
  --topic-arn $TOPIC_ARN \
  --message "Hello from SNS" \
  --region us-east-1
```

**Result**: Message → SNS → SQS queue → KEDA detects → Job spawns.

#### Event Format in Job

When SNS publishes to SQS, the message body contains the SNS envelope:

```json
{
  "Type": "Notification",
  "MessageId": "abc123",
  "TopicArn": "arn:aws:sns:us-east-1:123456789:demo-topic",
  "Message": "Hello from SNS",
  "Timestamp": "2026-09-17T04:00:00.000Z",
  "SignatureVersion": "1",
  "Signature": "...",
  "SigningCertURL": "...",
  "UnsubscribeURL": "..."
}
```

Job handler must parse the `Message` field:

```python
import json

def lambda_handler(event, context):
    # SQS message body contains SNS envelope
    sns_msg = json.loads(event.get('body', '{}'))
    actual_message = sns_msg.get('Message', '')
    
    logger.info(f"Received from SNS: {actual_message}")
    # Process...
```

#### LocalStack Example

In my POC, I use LocalStack to mock both SNS and SQS:

```bash
# LocalStack endpoints (same service on port 4566)
SNS_ENDPOINT="http://localhost:4566"
SQS_ENDPOINT="http://localhost:4566"

# Create topic
awslocal sns create-topic --name demo-topic --endpoint-url $SNS_ENDPOINT

# Create queue
awslocal sqs create-queue --queue-name demo-sns-queue --endpoint-url $SQS_ENDPOINT

# Subscribe (note: LocalStack URIs use 000000000000 as fake account)
awslocal sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:000000000000:demo-topic \
  --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:000000000000:demo-sns-queue \
  --endpoint-url $SNS_ENDPOINT
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
| `cron` | Schedule jobs (batch, cleanup, reports) | cron expression (e.g., `0 * * * *`) |
| `http` | HTTP polling | endpoint, method |
| `rabbitmq` | RabbitMQ queues | connection string, queue name |
| `nats` | NATS subjects | nats:// URL, subject |

#### Cron Trigger Deep Dive

The **cron scaler** enables scheduled, predictable workloads without requiring external job schedulers (like Jenkins, Airflow, or Lambda scheduled events).

**Use Cases**:
- Nightly batch reports (10 PM)
- Hourly data aggregation
- Daily cleanup jobs (delete temp files, purge old logs)
- Weekly reconciliation tasks
- Peak-hour scaling (scale up 9 AM–5 PM, scale down evenings)

**Cron Expression Format**: Standard Unix cron `(minute hour day month weekday)`

```
┌──────── minute (0–59)
│ ┌────── hour (0–23)
│ │ ┌──── day (1–31)
│ │ │ ┌── month (1–12)
│ │ │ │ ┌ weekday (0–6, where 0=Sunday)
│ │ │ │ │
* * * * *
```

**Common Patterns**:

| Pattern | Meaning | Example Use |
|---------|---------|-------------|
| `0 2 * * *` | 2 AM daily | Nightly batch |
| `0 */4 * * *` | Every 4 hours | Hourly cleanup, every 4 cycles |
| `0 9-17 * * 1-5` | 9 AM–5 PM weekdays | Business hours scaling |
| `0 22 * * *` | 10 PM daily | Start long-running job (finishes overnight) |
| `*/15 * * * *` | Every 15 minutes | Frequent polling/sync task |

**KEDA Cron Scaler Example** (scheduled batch job):

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: nightly-report-job
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: report-generator
          image: analytics:latest
          env:
          - name: REPORT_TYPE
            value: "daily"
  pollingInterval: 60
  minReplicaCount: 0
  maxReplicaCount: 5
  triggers:
  - type: cron
    metadata:
      timezone: America/New_York
      start: 0 22 * * *           # Start: 10 PM daily
      end: 30 23 * * *            # End: 10:30 PM daily
      desiredReplicas: "3"        # Run 3 concurrent jobs during window
```

**Flow**:
```
10:00 PM (22:00): KEDA sees cron matched → Creates 3 jobs
10:01 PM: Jobs running in parallel
10:25 PM: Jobs complete, jobs exit
10:31 PM: Outside window (end=10:30 PM) → KEDA scales down to 0
```

**Peak-Hours Example** (dynamic scaling based on time of day):

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: time-based-worker
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: worker
          image: myapp:latest
  triggers:
  - type: cron
    metadata:
      timezone: UTC
      start: 0 9 * * 1-5          # 9 AM on weekdays (Mon-Fri)
      end: 0 17 * * 1-5           # 5 PM on weekdays
      desiredReplicas: "20"       # Peak hours: 20 concurrent
  - type: cron
    metadata:
      timezone: UTC
      start: 0 17 * * *           # 5 PM daily
      end: 0 9 * * 1-5            # 9 AM next weekday
      desiredReplicas: "3"        # Off-peak: 3 concurrent
```

**Two triggers** = two time windows with different replica counts. KEDA applies whichever matches current time.

**Advantages vs Lambda Scheduled Events**:

| Aspect | KEDA Cron | Lambda EventBridge |
|--------|-----------|-------------------|
| **Scheduling** | Native cron | EventBridge rules (proprietary) |
| **Visibility** | Kubernetes Jobs (kubectl logs) | CloudWatch Logs only |
| **Timezone support** | IANA timezones (`America/New_York`, etc.) | UTC only (manual offset) |
| **Multiple windows** | Chain multiple cron triggers | One rule per schedule |
| **Cost** | Fixed node cost | Pay per invocation |
| **Concurrency** | Adjustable via desiredReplicas | Sequential (one invocation per trigger) |

**Cost Example** (scheduled batch):

```
Lambda: $0.20 per 1M + compute = ~$0.01/day for nightly job
KEDA: Fixed node cost $30/month whether jobs run or not
```

Lambda wins for infrequent jobs; KEDA wins if combined with queue-driven load.

---

#### Combining Cron + Event-Driven Scaling

Real power: Use cron to **pre-warm pools** before peak queue traffic:

```yaml
# Cron: Scale up at 8:50 AM (10 min before peak)
- type: cron
  metadata:
    timezone: America/New_York
    start: 50 8 * * 1-5
    end: 0 9 * * 1-5
    desiredReplicas: "5"        # Warm pool

# SQS: Event-driven scale during peak (9 AM–5 PM)
- type: aws-sqs-queue
  metadata:
    queueURL: "https://sqs.us-east-1.amazonaws.com/123456789/tasks"
    batchSize: "1"
  authenticationRef:
    name: aws-credentials
```

When 9 AM arrives, queue-driven scaling takes over. Pre-warmed pods handle spike without cold-start delay.

---

## Part 6: Analysis & Findings

### Governance Advantage

KEDA jobs are native Kubernetes workloads:
- ✅ Subject to the same RBAC policies
- ✅ Visible in `kubectl get pods`
- ✅ Integrated with existing observability stack (Prometheus, Grafana)
- ✅ Auditable via Kubernetes audit logs
- ✅ Use the same namespaces, quotas, and network policies

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

I modeled three scenarios:

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

The repo includes a full working example. To extend this work:
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

**Try it**: Clone the [keda-as-lambda](https://github.com/rohan-mathure/keda-as-lambda) repo and run `make demo-sqs N=10`. I built this to be runnable in minutes.

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

**Questions?** Open an issue on [GitHub](https://github.com/rohan-mathure/keda-as-lambda/issues).
