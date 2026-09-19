# Setup Verification Checklist for Users

Use this checklist to verify your environment is ready to run KEDA-as-Lambda experiments.

---

## ✅ Prerequisites Installation

### System Requirements
- [ ] **macOS** (10.15+) or **Linux** (Ubuntu 20.04+)
- [ ] **Docker Desktop** installed and running (`docker ps` works)
- [ ] At least 8GB RAM, 4 CPU cores available
- [ ] 20GB free disk space

### CLI Tools
```bash
# Install via Homebrew (macOS)
brew install k3d helm kubectl

# Or via direct download (see https://k3d.io, https://helm.sh, https://kubernetes.io)

# Verify installation
k3d version          # Should show v5.4+
helm version         # Should show v3.10+
kubectl version      # Should show v1.24+
docker version       # Should show Docker Desktop version
```

- [ ] `k3d` installed and working
- [ ] `helm` installed and working
- [ ] `kubectl` installed and working
- [ ] `docker` installed and working

### Python Packages
```bash
python3 --version   # Should be 3.9+

# Install dependencies
pip install matplotlib numpy boto3 awscli-local

# Verify
python3 -c "import json, matplotlib, numpy, statistics; print('✅ All imports OK')"
```

- [ ] Python 3.9+ installed
- [ ] matplotlib installed
- [ ] numpy installed
- [ ] boto3 installed
- [ ] awscli-local installed

---

## ✅ Repository Setup

```bash
git clone git@github.com:rohan-mathure/keda-as-lambda.git
cd keda-as-lambda

# Verify directory structure
ls -la cluster/ keda/ workload/ load-generator/ optimization-analysis/
```

- [ ] Repository cloned successfully
- [ ] All subdirectories present (`cluster/`, `keda/`, `workload/`, `load-generator/`, `optimization-analysis/`)
- [ ] Makefile present at root
- [ ] README.md present and readable

---

## ✅ Analysis Scripts (No Cluster Required)

These tests verify the standalone analysis pipeline without needing a Kubernetes cluster.

### 1. Cost Model Test
```bash
python3 optimization-analysis/experiments/cost_model_arm.py
```

Expected output:
```
🔬 KEDA vs Lambda Cost Analysis
================================================================================
Scenario: Dev/Test (10,000 invocations/month)
  AWS Lambda: $0/year
  KEDA ARM: $286/year
...
Break-Even Analysis: KEDA cheaper at 5M+/month
```

- [ ] Cost model runs without errors
- [ ] Shows cost comparison across scales
- [ ] No missing dependencies errors

### 2. Statistical Analysis Test
```bash
cd optimization-analysis/experiments
python3 experiment_runner.py
```

Expected output:
```
EXPERIMENT RUNNER: 10 trials per pattern
📊 Baseline (cron)
  Mean: 4500ms, Median: 4500ms, Std Dev: 527ms
📊 Warm Pool (1s poll)
  Mean: 913ms, Median: 906ms, Std Dev: 126ms
✅ Results saved to ../results/statistical_results.json
```

- [ ] Experiment runner completes without errors
- [ ] Generates `statistical_results.json`
- [ ] Shows 6 patterns with statistics
- [ ] No path errors (`../results/` found)

### 3. Graph Generation Test
```bash
cd optimization-analysis/experiments
python3 statistical_graphs.py
```

Expected output:
```
GENERATING STATISTICAL GRAPHS
✅ Saved: graph_10_boxplot_distributions.png
✅ Saved: graph_11_percentile_comparison.png
✅ Saved: graph_12_consistency_analysis.png
✅ Saved: graph_13_violin_distributions.png
✅ Saved: graph_14_summary_table.png
```

- [ ] Graph generation completes without errors
- [ ] 5 graphs created (graph_10 through graph_14)
- [ ] PNG files are > 100KB each (valid images)

### 4. Subsecond Polling Analysis Test
```bash
cd optimization-analysis/experiments
python3 subsecond_polling_analysis.py
```

Expected output:
```
SUBSECOND POLLING ANALYSIS
📊 Detection Latency vs Cost Trade-off
Polling Interval | p50 Latency | API Calls/hr | Annual Cost
100ms (subsecond)    50ms  36000/hr  $127/yr
500ms                250ms  7200/hr  $25/yr
1s                   500ms  3600/hr  $13/yr
30s (default)        15s     120/hr  $0.42/yr
```

- [ ] Polling analysis completes without errors
- [ ] Shows trade-offs for 7 polling intervals
- [ ] Generates `subsecond_polling_analysis.json`
- [ ] Includes SQS rate limit discussion

### 5. Scale Analysis Test
```bash
cd optimization-analysis/experiments
python3 scale_analysis.py
python3 scale_graphs.py
```

Expected output:
```
KEDA COST & LATENCY ANALYSIS AT SCALE
Scale: 100,000 invocations/month
  Lambda: $0 ← CHEAPEST
  KEDA ARM: $286
Scale: 1,000,000 invocations/month
  Lambda: $20 ← CHEAPEST
Scale: 10,000,000 invocations/month
  KEDA ARM: $286 ← CHEAPEST
✅ Results saved to results/scale_analysis.json
✅ Saved: graph_6_scale_costs.png
✅ Saved: graph_7_latency_comparison.png
✅ Saved: graph_8_breakeven_volume.png
✅ Saved: graph_9_prewarming_effect.png
```

- [ ] Scale analysis completes without errors
- [ ] Generates `scale_analysis.json`
- [ ] 4 scale comparison graphs created
- [ ] Cost break-even identified at 5M invocations/month

### 6. Results Verification
```bash
cd optimization-analysis/results

# Check all data files exist
ls -lh *.json

# Verify JSON is valid
for f in *.json; do python3 -m json.tool "$f" > /dev/null && echo "✅ $f"; done

# Check all graphs exist
ls -lh graph_*.png | wc -l  # Should show 15
```

- [ ] 5 JSON result files present (exp_comprehensive_results.json, scale_analysis.json, statistical_results.json, subsecond_polling_analysis.json, exp1_existing_jobs.json)
- [ ] All JSON files are valid (parseable)
- [ ] 15 PNG graphs present
- [ ] Graph files are > 100KB each

---

## ✅ Cluster Setup (Optional, Requires k3d + kubectl)

If you want to run the live Kubernetes cluster demo:

### 1. Cluster Creation
```bash
make cluster-up
# Expected: k3d cluster "keda-lambda" created, nodes ready
kubectl get nodes
# Expected: 3 nodes in Ready state (1 server, 2 agents)
```

- [ ] Cluster creates successfully
- [ ] `kubectl get nodes` shows 3 ready nodes
- [ ] No error messages about k3d or Docker

### 2. LocalStack Setup (SQS/SNS Mocking)
```bash
make localstack-up
make init-aws
# Expected: LocalStack pod running, SQS queues created
kubectl get pods -n localstack
kubectl get queues  # If supported
```

- [ ] LocalStack pod is Running
- [ ] SQS queues created (demo-queue, demo-sns-queue)
- [ ] SNS topic created (demo-topic)

### 3. KEDA Installation
```bash
make keda-up
# Expected: KEDA operator pod running
kubectl get pods -n keda
```

- [ ] KEDA operator pod is Running in `keda` namespace
- [ ] No installation errors

### 4. Workload Build
```bash
make build
# Expected: Docker image built, imported into k3d
docker images | grep keda-demo
```

- [ ] `keda-demo:latest` image exists locally
- [ ] Image successfully imported into k3d

### 5. Demo Run
```bash
make demo-sqs N=5
# Watch jobs spawn
kubectl get jobs -n demo -w
# After ~10 seconds, jobs should complete
```

- [ ] Jobs are created in `demo` namespace
- [ ] Jobs complete successfully
- [ ] Logs available: `kubectl logs -n demo -l app=keda-demo`

### 6. Cleanup
```bash
make cluster-down
# Expected: cluster destroyed, all resources cleaned up
kubectl get clusters  # Should not show keda-lambda
```

- [ ] Cluster destroyed successfully
- [ ] No hanging resources (check Docker: `docker ps`)

---

## ✅ Troubleshooting

### Python Script Errors

**Error: `FileNotFoundError: ../results/...`**
- **Cause**: Script run from wrong directory
- **Fix**: `cd optimization-analysis/experiments/` before running

**Error: `ModuleNotFoundError: No module named 'matplotlib'`**
- **Cause**: Missing Python packages
- **Fix**: `pip install matplotlib numpy boto3`

**Error: `matplotlib.deprecation.Deprecation: ...`**
- **Cause**: Matplotlib version mismatch (cosmetic warning)
- **Fix**: Can ignore; graphs still generate correctly

### Cluster Errors

**Error: `k3d: command not found`**
- **Cause**: k3d not installed
- **Fix**: `brew install k3d` (macOS) or download from https://k3d.io

**Error: `Docker daemon is not running`**
- **Cause**: Docker Desktop not started
- **Fix**: Open Docker Desktop or start Docker service

**Error: `kubectl: connection refused`**
- **Cause**: Cluster not running
- **Fix**: `make cluster-up` first

**Error: `LocalStack pod not ready`**
- **Cause**: Pod still starting (takes ~30 seconds)
- **Fix**: Wait 30 seconds, then `kubectl get pods -n localstack`

---

## ✅ What Success Looks Like

After all checks pass, you should have:

1. **Analysis scripts working**: Cost model, statistics, graphs all generate
2. **15 publication-ready graphs**: In `optimization-analysis/results/`, 300 DPI PNG
3. **JSON result files**: For your own data processing/visualization
4. **Optional cluster running**: If you chose to set it up (demo SQS → jobs → complete)
5. **Reproducible setup**: All commands in README should work without modification

---

## ✅ Next Steps

1. **Review findings**: Read `optimization-analysis/SCALE_ANALYSIS.md`
2. **Customize for your workload**: Edit `experiments/cost_model_arm.py` with your specs
3. **Run live demo**: Execute `make demo-sqs` if you have cluster running
4. **Adapt experiments**: Modify patterns in `experiment_runner.py` for your use case
5. **Publish results**: Use graphs in presentations, articles, or reports

---

## ✅ Getting Help

If you hit issues:

1. **Check this checklist** — Most issues are covered above
2. **Read README.md** — Quick-start and architecture explanation
3. **Review Makefile** — `make help` shows all targets
4. **Check Kubernetes logs**: `kubectl logs -n <namespace> <pod>`
5. **Verify prerequisites** — Docker running, k3d installed, Python packages available

---

**Ready to experiment? Start with the analysis scripts (no cluster needed), then optionally set up the cluster for the full demo.**

Good luck! 🚀
