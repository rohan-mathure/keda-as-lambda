# KEDA Optimization Analysis

Performance benchmarks and cost analysis for KEDA-as-Lambda optimizations.

## Experiments

Benchmarking suite measuring performance improvements from:
1. Image optimization (Alpine, Distroless variants)
2. Polling interval tuning (1s-30s latency trade-offs)
3. Warm pool pattern (fixed cost vs per-message scaling)
4. ARM64 pricing analysis (Graviton3 vs x86)

## Scripts

- `benchmark_cron_comprehensive.py` — Extract cron job metrics, calculate statistics
- `benchmark.py` — SQS-based latency measurement
- `benchmark_cron.py` — Cron-based baseline (no SQS needed)
- `cost_model_arm.py` — Cost comparison (Lambda vs KEDA, ARM pricing)
- `generate_graphs.py` — Create publication-quality visualizations

## Results

### Data Files
- `exp_comprehensive_results.json` — Benchmark results (20 trials, estimates)
- `exp1_existing_jobs.json` — Cron job timing data
- `cost_model_output.txt` — Cost model output
- `exp2_images.csv` — Image size comparison

### Graphs (300 DPI, publication-ready)
1. `graph_1_image_optimization.png` — Image sizes + startup times
2. `graph_2_polling_tradeoff.png` — Latency vs API cost trade-off
3. `graph_3_cost_breakeven.png` — Lambda vs KEDA at scale
4. `graph_4_optimization_stack.png` — Cumulative optimization impact
5. `graph_5_warmpool_economics.png` — Fixed vs per-message cost

## Quick Start

```bash
# Run benchmark (extracts existing cron job data)
python3 experiments/benchmark_cron_comprehensive.py

# Generate graphs
python3 experiments/generate_graphs.py

# View results
ls results/graph_*.png
cat results/exp_comprehensive_results.json | python3 -m json.tool
```

## Key Findings

**Cost Break-even**: KEDA cheaper at 5M+ invocations/month  
**Image Optimization**: 50% size reduction (Alpine) → 15% latency improvement  
**Polling Trade-off**: 1s polling = 0.5s latency, +$1.24/year SQS cost  
**Warm Pool**: $29/month fixed cost, break-even at 1M invocations/month  
**ARM Savings**: 36% cheaper than x86 spot nodes

---

**Note**: Medium article (MEDIUM_ARTICLE_PART2.md) is published separately. See Part 2 article for full analysis and visualizations.
