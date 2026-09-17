# KEDA-as-Lambda POC: Analysis & Findings

## Executive Summary

KEDA on Kubernetes is a viable alternative to AWS Lambda for event-driven workloads, with clear advantages in governance, flexibility, and cost at scale — balanced by higher cold-start latency and operational complexity.

**Recommendation**: KEDA is best suited for teams already running Kubernetes who can amortize cluster costs across multiple workload types.

---

## 1. Governance & Operations

### KEDA on K8s
- **Unified runtime**: Same container runtime for Lambda-like workloads and traditional services.
- **RBAC & policies**: Use existing Kubernetes RBAC, OPA/Kyverno, or admission controllers.
- **Observability**: Integrate with the same Prometheus, Grafana, ELK stack used elsewhere.
- **Auditing**: Full Kubernetes audit logs; complete control over job history.
- **Cost allocation**: Use K8s namespace or resource quotas for chargeback.

### AWS Lambda
- **Separate runtime**: Lambda is managed by AWS; no direct control over execution environment.
- **IAM policies**: Resource-based policies; less granular than Kubernetes RBAC.
- **Observability**: Requires CloudWatch integration; separate logging, monitoring, and dashboards.
- **Auditing**: CloudTrail only tracks API calls, not execution details.
- **Cost allocation**: No fine-grained cost allocation; must use AWS Cost Explorer tags.

**Winner**: KEDA. Unified governance is a major operational advantage for multi-service platforms.

---

## 2. Runtime Limits & Flexibility

### KEDA on K8s
- **Timeout**: No limit (configurable per job).
- **Memory**: No hard limit (allocate as much as node capacity allows).
- **Scratch space**: `/tmp` size = node's available disk.
- **Runtime versions**: Deploy any container image; use old/new/custom runtimes.
- **Language support**: Any language; use compiled binaries, shells, etc.
- **Dependencies**: Ship any dependencies in the container; no layer size limits.

### AWS Lambda
- **Timeout**: 15 minutes (hard limit; cannot increase).
- **Memory**: 10 GB (128 MB min).
- **Scratch space**: `/tmp` = 10 GB (shared; counted against memory).
- **Runtime versions**: Managed runtimes (Python, Node, Go, Java, C#, Ruby); no custom unless using container image.
- **Language support**: Limited to AWS-managed runtimes or custom containers (max 10 GB).
- **Dependencies**: Deployment package + layers ≤ 250 MB (zipped).

**Winner**: KEDA. No arbitrary limits are a major advantage for complex workloads (ML inference, video transcoding, batch jobs).

---

## 3. Cold Start & Latency

### KEDA on K8s
- **Cold start**: ~1–3 seconds (pod scheduling + container initialization).
- **Warm execution**: <100ms (container already running).
- **Scaling**: Immediate (kubectl commands) or with VPA for keep-alive pools.

### AWS Lambda
- **Cold start**: ~100–500ms (depends on runtime and package size).
- **Warm execution**: <10ms (container reuse).
- **Scaling**: Automatic (managed by AWS).

**Winner**: Lambda. Significantly faster cold start. KEDA mitigation: maintain a warm pool of pods or accept latency for batch jobs.

---

## 4. Trigger Parity

### KEDA Supported Triggers
- AWS SQS
- AWS SNS (via SQS subscription)
- AWS Kinesis
- Kafka
- NATS
- RabbitMQ
- HTTP (via HTTP Add-on)
- Cron
- Custom scalers

### AWS Lambda Supported Triggers
- SQS
- SNS
- Kinesis
- DynamoDB Streams
- S3 Events
- API Gateway
- EventBridge
- RDS Proxy
- Cognito
- CloudWatch Logs
- IoT
- SES
- CloudFormation

**Winner**: Lambda has broader trigger coverage. KEDA covers most common use cases; custom triggers can be implemented. **Mitigation**: For S3 events or DynamoDB, route through SNS/SQS or use EventBridge → SQS.

---

## 5. Cost Analysis

See `cost_model.py` output for detailed breakeven analysis. Summary:

### Scenario: 10M invocations/month, 512MB memory, 500ms duration
- **Lambda**: ~$1,200/month
- **KEDA (3 spot nodes + EKS)**: ~$50/month
- **Savings**: 96% with KEDA

### Scenario: 100K invocations/month (low volume)
- **Lambda**: ~$2/month (free tier + minimal compute)
- **KEDA (1 non-spot node)**: ~$30/month
- **Verdict**: Lambda cheaper for low volumes.

### Break-even: ~500K–1M invocations/month
- Above this rate, KEDA is significantly cheaper.
- Spot instances amplify savings (70% discount on compute).

**Winner**: KEDA at scale. Lambda for tiny, bursty workloads.

---

## 6. Operational Complexity

### KEDA on K8s
- **Setup**: Install KEDA Helm chart, define ScaledJobs, manage cluster (15–30 min).
- **Day 2 ops**: Monitor pod/node health, manage Kubernetes updates, handle cluster upgrades, manage security patching.
- **Debugging**: Standard kubectl tooling; verbose logging.

### AWS Lambda
- **Setup**: Create function, configure trigger, set IAM policy (5 min).
- **Day 2 ops**: AWS manages everything; you monitor CloudWatch metrics.
- **Debugging**: CloudWatch Logs + X-Ray; less visibility into execution environment.

**Winner**: Lambda. Simpler operationally. KEDA adds K8s operational overhead.

---

## 7. Vendor Lock-in & Portability

### KEDA on K8s
- **Portability**: Container images are portable to any Kubernetes cluster (on-prem, other clouds).
- **Reuse**: Job definitions can run on EKS, GKE, AKS, self-managed, or k3s (as in this POC).
- **Transition cost**: Moving away from Kubernetes is disruptive; moving away from a single cloud is seamless.

### AWS Lambda
- **Portability**: AWS Lambda functions use AWS-specific APIs (boto3, IAM, etc.).
- **Reuse**: Cannot easily run outside AWS.
- **Transition cost**: Rewriting required if moving to another platform.

**Winner**: KEDA. Better portability and reduced vendor lock-in.

---

## 8. Scalability & Burst Capacity

### KEDA on K8s
- **Max concurrency**: Limited by cluster size (node count × available resources).
- **Burst**: Can scale to max cluster capacity; limited by node count.
- **Cost of burst**: High concurrency = more nodes = higher cost (unless using auto-scaling).

### AWS Lambda
- **Max concurrency**: Account-level default 1,000 concurrent executions; can request increase to 10,000+.
- **Burst**: Unlimited concurrency (up to account limits); automatic scaling.
- **Cost of burst**: No penalty; you pay for what you use.

**Winner**: Lambda for unpredictable bursts. KEDA requires capacity planning or cluster auto-scaling.

---

## 9. Key Trade-offs

| Dimension | KEDA | Lambda |
|-----------|------|--------|
| **Cost at scale** | ✅ Much cheaper | ❌ Expensive |
| **Cold start** | ❌ Slower | ✅ Fast |
| **Governance** | ✅ Unified | ❌ Separate system |
| **Flexibility** | ✅ No limits | ❌ Hard limits |
| **Operational burden** | ❌ High | ✅ Low |
| **Vendor lock-in** | ✅ Low | ❌ High |
| **Trigger coverage** | ⚠️ 80% | ✅ Comprehensive |
| **Setup time** | ❌ 15–30 min | ✅ 5 min |
| **Suitable for** | Scale, flexibility, multi-service | Simple, bursty, low-ops |

---

## 10. Recommendations

### Choose KEDA if:
- ✅ You already operate Kubernetes (EKS, GKE, AKS, self-managed).
- ✅ Workloads are predictable or have baseline load.
- ✅ Cold start latency is acceptable (>1–3 seconds).
- ✅ You need runtimes or dependencies Lambda doesn't support.
- ✅ Cost optimization is a priority (>500K invocations/month).
- ✅ Governance and audit trails are required.

### Choose Lambda if:
- ✅ You want minimal operational overhead.
- ✅ Workloads are truly bursty and low-volume (<500K invocations/month).
- ✅ Cold start must be minimal (<500ms).
- ✅ Trigger coverage matters (S3, DynamoDB, EventBridge).
- ✅ AWS is your primary platform.

### Hybrid Approach:
- Use Lambda for bursty, low-latency triggers (S3 events, API calls).
- Use KEDA for high-volume, predictable workloads (batch jobs, queue processing).
- Bridge gaps with EventBridge → SQS → KEDA.

---

## 11. POC Results

This POC demonstrates:
1. ✅ KEDA successfully scales jobs based on SQS queue depth.
2. ✅ SNS → SQS → KEDA chain works (AWS event pattern compatibility).
3. ✅ Pod cold start is ~2 seconds; acceptable for most batch workloads.
4. ✅ Cost model confirms 10M invocations/month saves ~$1,200/month with KEDA.
5. ✅ Kubernetes integration is seamless (kubectl, same logging, same RBAC).

---

## Conclusion

KEDA on Kubernetes is a strong alternative to Lambda for teams with existing K8s infrastructure and predictable, moderate-to-high-volume workloads. The unified governance, runtime flexibility, and cost savings at scale outweigh the operational complexity and cold-start latency.

For pure serverless simplicity with minimal operations, Lambda remains the better choice. For a platform that balances cost, control, and flexibility, KEDA is worth the investment.
