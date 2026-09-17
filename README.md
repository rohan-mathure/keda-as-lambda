# KEDA-as-Lambda POC

Proof of concept: run Lambda-like workloads on KEDA + k3s instead of AWS Lambda.

**Why**: Same K8s governance, no Lambda restrictions (runtime, memory, timeout), lower cost via spot instances.

**Read the analysis**: [MEDIUM_ARTICLE_DRAFT.md](MEDIUM_ARTICLE_DRAFT.md) (detailed comparison, cost model, config breakdown)
**Read the findings**: [analysis/ANALYSIS.md](analysis/ANALYSIS.md) (governance, trade-offs, recommendations)

## Prerequisites

```bash
brew install k3d helm kubectl
pip install awscli-local boto3
# Docker Desktop running and configured
```

## Quick Start

```bash
# 1. Create cluster and install components
make cluster-up
make localstack-up
make init-aws
make keda-up
make build

# 2. Run demo: send 5 messages to SQS, watch jobs spawn
make demo-sqs N=5
kubectl get jobs -n demo -w

# 3. Check logs
kubectl logs -n demo -l app=keda-demo

# 4. Generate cost analysis
make cost-model

# 5. Cleanup
make cluster-down
```

## Architecture

- **k3d cluster**: k3s in Docker, 1 server + 2 agents
- **LocalStack**: mocks SQS, SNS (replaces AWS)
- **KEDA**: watches SQS queues, spawns jobs per N messages
- **ScaledJob**: Lambda-like: one job = one invocation, no persistent pods

## Files

- `cluster/` — k3d cluster config + LocalStack deployment
- `keda/` — KEDA operator values + ScaledJob definitions
- `workload/` — Python job handler (mocks Lambda handler)
- `load-generator/` — sends test messages to queues
- `analysis/` — cost model + final comparison

## Demos

### SQS Trigger
```bash
make demo-sqs N=20
# Sends 20 messages → 20 jobs spawn → jobs process & complete
```

### SNS Trigger (SNS → SQS subscription → jobs)
```bash
make demo-sns N=20
# Publishes to SNS → auto-forwarded to SQS → jobs spawn
```

## Next Steps

1. Verify cluster and jobs run successfully
2. Review `analysis/ANALYSIS.md` for governance, runtime, cost comparison
3. Adjust `analysis/cost_model.py` inputs for your workload
