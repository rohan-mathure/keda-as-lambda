# Testing Guide: KEDA-as-Lambda POC

This guide verifies all functionality works as expected. Follow step-by-step or run the full test script.

## Prerequisites

```bash
# Check versions
k3d version
helm version
kubectl version --client
python3 --version
docker --version

# Verify installed
which k3d helm kubectl python3 docker
```

## Quick Verification (5 min)

Already have a cluster? Skip to step 3.

### 1. Create Cluster & KEDA

```bash
make cluster-up          # ~60s
make keda-up             # ~30s
make build               # ~10s
```

**Expected output**:
- `cluster-up`: "Cluster ready."
- `keda-up`: "KEDA ready."
- `build`: "Image ready."

### 2. Verify Cluster

```bash
kubectl get nodes
# Expected: 3 nodes (1 server, 2 agents) all Ready

kubectl get pods -n keda
# Expected: keda-operator, keda-operator-metrics-apiserver pods Running
```

### 3. Test Cron Trigger (No Dependencies)

```bash
# Apply cron ScaledJob
kubectl apply -f keda/scaled-job-cron.yaml -n demo

# Check if job created (should see 1-2 jobs within 30s)
kubectl get jobs -n demo

# View logs
kubectl logs -n demo -l job-name=demo-cron-job-<TAB-TO-COMPLETE>

# Expected: Handler logs showing message processing
```

### 4. Test Cost Model

```bash
make cost-model

# Expected: 3 cost scenarios with break-even analysis printed
```

## Full Test (15 min) - SQS + SNS

### 1. Deploy LocalStack (Optional - Skip if Docker Pull Issues)

```bash
make localstack-up    # ~120s (pulls large image)
make init-aws         # ~10s
```

**Troubleshooting**: If LocalStack pod stuck in `ContainerCreating`:
- Check disk space: `df -h`
- Check network: `docker pull localstack/localstack:3`
- Skip LocalStack, use cron-only tests

### 2. Test SQS Trigger

```bash
# Check LocalStack pod is ready
kubectl get pods -n localstack

# Apply SQS ScaledJob
kubectl apply -f keda/scaled-job-sqs.yaml -n demo

# Send 3 test messages
make demo-sqs N=3

# Watch jobs spawn (should see 3 jobs within 15s)
kubectl get jobs -n demo -w

# Check logs
kubectl logs -n demo -l app=keda-demo --tail=20
```

### 3. Test SNS → SQS Trigger

```bash
# Apply SNS ScaledJob
kubectl apply -f keda/scaled-job-sns.yaml -n demo

# Publish 3 messages to SNS
make demo-sns N=3

# Watch jobs spawn (should see 3 jobs within 15s)
kubectl get jobs -n demo -w

# Check logs
kubectl logs -n demo -l app=keda-demo --tail=20
```

## Cleanup

```bash
make clean                # Delete demo namespace and LocalStack
make cluster-down         # Destroy k3d cluster (optional)
```

## Validation Checklist

- [x] `make cluster-up` creates 3-node k3s cluster
- [x] `make keda-up` installs KEDA operator
- [x] `make build` builds and imports workload image
- [x] `make demo-sqs N=3` sends 3 messages to SQS queue
- [x] `make demo-sns N=3` publishes 3 messages to SNS topic
- [x] Cron trigger spawns jobs automatically every hour
- [x] `make cost-model` generates cost analysis
- [x] `kubectl get jobs -n demo` shows completed jobs
- [x] `kubectl logs` shows handler output (message received, processing, complete)
- [x] `.devcontainer/` setup works with VS Code
- [x] `devbox.json` works with Devbox/Flox
- [x] All Python dependencies installable

## Troubleshooting

### Cluster Issues

**Problem**: `k3d cluster create` fails
```bash
# Check Docker running
docker ps

# Try with verbose logging
k3d cluster create --config cluster/k3d-config.yaml -v
```

**Problem**: Nodes not Ready
```bash
# Check node status
kubectl describe node k3d-keda-lambda-server-0

# Check pod logs
kubectl logs -n kube-system -l k8s-app=kube-proxy
```

### KEDA Issues

**Problem**: ScaledJob not creating jobs
```bash
# Check KEDA logs
kubectl logs -n keda -l app.kubernetes.io/name=keda-operator --tail=50

# Check ScaledJob status
kubectl describe scaledjob demo-cron-job -n demo
```

**Problem**: Jobs not progressing past Pending
```bash
# Check pod events
kubectl describe pod -n demo -l app=keda-demo

# Check node capacity
kubectl describe nodes

# Check image imported
docker images | grep keda-demo
k3d image list
```

### LocalStack Issues

**Problem**: LocalStack pod stuck in ContainerCreating
```bash
# Check pod logs
kubectl logs -n localstack localstack-*

# Check node disk space
df -h /tmp

# Try without LocalStack (use cron demo instead)
```

**Problem**: SQS/SNS commands timeout
```bash
# Check LocalStack service
kubectl get svc -n localstack

# Port-forward to test
kubectl port-forward -n localstack svc/localstack 4566:4566

# In another terminal
awslocal --endpoint-url http://localhost:4566 sqs list-queues
```

### Load Generator Issues

**Problem**: `make demo-sqs` fails to connect
```bash
# Check LocalStack is running
kubectl get pods -n localstack

# Check boto3 installed
python3 -c "import boto3; print(boto3.__version__)"

# Test manually
python3 load-generator/send_messages.py --help
```

## Dev Experiment Ideas

1. **Scale Test**: `make demo-sqs N=100` - send 100 messages, watch scale-up
2. **Timeout Test**: Modify handler.py to run longer, test visibilityTimeout
3. **Cost Analysis**: Adjust `analysis/cost_model.py` inputs for your workload
4. **Custom Trigger**: Add HTTP trigger instead of SQS (see KEDA docs)
5. **Observability**: Add Prometheus scraping to measure job duration
6. **Multi-region**: Deploy SNS topic in different region, test fanout

## Performance Baseline

Expected timings on 2024 MacBook Pro (M3 Max):

| Operation | Time | Notes |
|-----------|------|-------|
| `make cluster-up` | ~60s | k3s setup + node startup |
| `make keda-up` | ~30s | Helm install |
| `make build` | ~10s | Docker build + import |
| `make demo-sqs N=10` | ~20s total | Send + job startup + completion |
| Pod cold-start | ~2-3s | From message to job running |
| Job completion | ~4-5s | Handler execution time (mocked work) |
| Cron trigger | ~60s | Every hour (configurable) |

## Next Steps

- [ ] Clone repo locally or use devcontainer
- [ ] Run quick verification (step 1-4)
- [ ] Experiment with cost-model for your workload
- [ ] Try scaling tests (send 100+ messages)
- [ ] Read MEDIUM_ARTICLE_DRAFT.md for details
- [ ] Modify handler.py for your use case
- [ ] Deploy to real AWS (replace LocalStack endpoints)

---

**Issues?** Open [GitHub issue](https://github.com/rohan-mathure/keda-as-lambda/issues)
