# Quick Start: KEDA-as-Lambda POC

Get up and running in 5 minutes.

## 1. Clone & Test

```bash
git clone git@github.com:rohan-mathure/keda-as-lambda.git
cd keda-as-lambda

# Verify setup (should show 29/29 tests passing)
./test.sh
```

## 2. One-Command Setup

```bash
# Create cluster, install KEDA, build workload
make cluster-up && make keda-up && make build
```

**Time**: ~90 seconds | **Result**: Ready to demo

## 3. Run Demo (pick one)

### Simplest: Cron Trigger (no dependencies)
```bash
# Watch jobs spawn automatically every hour
kubectl apply -f keda/scaled-job-cron.yaml -n demo
kubectl get jobs -n demo -w

# Stop watching: Press Ctrl+C
```

### Full: SQS + SNS Triggers
```bash
# Setup LocalStack (SQS/SNS mock)
make localstack-up && make init-aws

# Send 5 test messages to SQS
make demo-sqs N=5

# Watch 5 jobs spawn
kubectl get jobs -n demo -w

# View logs
kubectl logs -n demo -l app=keda-demo --tail=30
```

## 4. Analyze

```bash
# View cost comparison
make cost-model

# Read detailed analysis
cat MEDIUM_ARTICLE_DRAFT.md
cat analysis/ANALYSIS.md
```

## 5. Cleanup

```bash
make clean              # Delete demo namespace
make cluster-down       # Destroy cluster (optional)
```

---

## Makefile Cheatsheet

| Command | What It Does | Time |
|---------|-------------|------|
| `make cluster-up` | Create k3d cluster | ~60s |
| `make keda-up` | Install KEDA | ~30s |
| `make build` | Build workload image | ~10s |
| `make demo-sqs N=5` | Send 5 SQS messages | ~10s |
| `make demo-sns N=5` | Publish 5 SNS messages | ~10s |
| `make cost-model` | Generate cost analysis | ~5s |
| `make clean` | Delete demo namespace | ~5s |
| `make cluster-down` | Destroy cluster | ~30s |

---

## What's Happening?

```
You (make demo-sqs N=5)
         ↓
   Send 5 messages to SQS
         ↓
   KEDA polls queue every 5s
         ↓
   KEDA sees 5 messages
         ↓
   KEDA creates 5 Kubernetes Jobs
         ↓
   5 pods spin up (~2-3s each)
         ↓
   Python handler processes each message
         ↓
   Pods exit, jobs complete
         ↓
   You see: 5 completed jobs in kubectl
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `k3d not found` | `brew install k3d helm kubectl` |
| Cluster not ready | `kubectl get nodes` → should show 3 Ready |
| KEDA not running | `make keda-up` |
| Image not imported | `make build` |
| Jobs not spawning | `kubectl logs -n keda -l app.kubernetes.io/name=keda-operator` |

More troubleshooting: See [TESTING.md](TESTING.md)

---

## Dev Experiments

```bash
# Scale test: send 50 messages
make demo-sqs N=50

# Watch peak scaling
kubectl top nodes
kubectl top pods -n demo

# Check cost for your workload
# Edit analysis/cost_model.py, adjust invocations/month
python3 analysis/cost_model.py

# Try SNS → SQS chain
make localstack-up
make init-aws
make demo-sns N=10

# Modify handler for your use case
# Edit workload/handler.py
make build
make demo-sqs N=5
```

---

## Next Steps

1. **Read the article**: `MEDIUM_ARTICLE_DRAFT.md` — full details, cost analysis, trade-offs
2. **See the analysis**: `analysis/ANALYSIS.md` — governance, cold-start, when to use KEDA vs Lambda
3. **Explore configs**: `keda/scaled-job-*.yaml` — all trigger types explained
4. **Run tests**: `./test.sh` — verify everything works
5. **Deploy to AWS**: Replace LocalStack endpoints with real SQS/SNS, deploy to EKS

---

## Files You'll Care About

- **`Makefile`**: All commands (run `make help`)
- **`workload/handler.py`**: Your Lambda-like function (modify this)
- **`keda/scaled-job-*.yaml`**: Trigger definitions (copy & adapt)
- **`MEDIUM_ARTICLE_DRAFT.md`**: Everything explained in detail
- **`analysis/cost_model.py`**: Plug in your numbers, see savings
- **`test.sh`**: Verify setup works

---

**Ready?** Run: `make cluster-up && make keda-up && make build && make demo-sqs N=3`

Issues? See [TESTING.md](TESTING.md) or open [GitHub issue](https://github.com/rohan-mathure/keda-as-lambda/issues).
