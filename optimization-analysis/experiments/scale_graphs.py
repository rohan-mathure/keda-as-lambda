#!/usr/bin/env python3
"""Generate graphs for scale analysis."""

import matplotlib.pyplot as plt
import numpy as np

def graph_scale_costs():
    """Graph costs across scales."""
    fig, ax = plt.subplots(figsize=(14, 6))

    scales = [100_000, 1_000_000, 10_000_000]
    scale_labels = ["100K", "1M", "10M"]

    lambda_costs = [0, 20, 942]
    keda_30s_costs = [449, 449, 449]
    keda_1s_costs = [461, 461, 461]
    warmpool_costs = [360, 360, 360]
    arm_costs = [286, 286, 286]

    x = np.arange(len(scale_labels))
    width = 0.15

    ax.bar(x - 2*width, lambda_costs, width, label="Lambda", color="#FF6B6B")
    ax.bar(x - width, keda_30s_costs, width, label="KEDA ScaledJob (30s)", color="#FFA07A")
    ax.bar(x, keda_1s_costs, width, label="KEDA ScaledJob (1s)", color="#FFD700")
    ax.bar(x + width, warmpool_costs, width, label="Warm Pool", color="#4ECDC4")
    ax.bar(x + 2*width, arm_costs, width, label="KEDA ARM (30s)", color="#45B7D1")

    ax.set_ylabel("Annual Cost ($)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Invocations per Month", fontsize=12, fontweight="bold")
    ax.set_title("Annual Cost Comparison Across Scales", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(scale_labels)
    ax.legend(fontsize=10, loc="upper left")
    ax.set_ylim(0, 1200)

    # Annotation
    ax.text(0, 500, "Lambda\nwins", ha="center", fontsize=9, fontweight="bold", color="red")
    ax.text(2, 600, "KEDA wins\n70% savings", ha="center", fontsize=9, fontweight="bold", color="green")

    plt.tight_layout()
    plt.savefig("../results/graph_6_scale_costs.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_6_scale_costs.png")
    plt.close()

def graph_latency_comparison():
    """Graph latency at different approaches."""
    fig, ax = plt.subplots(figsize=(12, 6))

    approaches = ["Lambda", "Warm Pool\n(1s poll)", "KEDA Warm\n(1s poll)", "KEDA Cold\n(1s poll)", "KEDA\n(30s poll)"]
    latencies = [0.2, 1.0, 3.3, 4.5, 19.0]
    colors = ["#FF6B6B", "#4ECDC4", "#FFA07A", "#FFD700", "#D3D3D3"]

    bars = ax.barh(approaches, latencies, color=colors, edgecolor="black", linewidth=2)

    ax.set_xlabel("p50 Latency (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("Job Startup Latency: Cold vs Warm vs Lambda", fontsize=14, fontweight="bold")
    ax.set_xlim(0, 21)

    # Add value labels
    for i, (bar, latency) in enumerate(zip(bars, latencies)):
        ax.text(latency + 0.3, bar.get_y() + bar.get_height()/2, f"{latency:.1f}s",
                va="center", fontweight="bold", fontsize=11)

    # Lambda baseline annotation
    ax.axvline(x=0.2, color="red", linestyle="--", linewidth=2, alpha=0.5, label="Lambda baseline")

    plt.tight_layout()
    plt.savefig("../results/graph_7_latency_comparison.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_7_latency_comparison.png")
    plt.close()

def graph_breakeven_volume():
    """Graph break-even point."""
    fig, ax = plt.subplots(figsize=(12, 6))

    volumes = np.logspace(4, 7, 50)  # 10K to 10M
    lambda_costs = [v * 0.0000002 * 12 + (v * 1 * 512/1024 * 0.0000166667) * 12 for v in volumes]
    keda_costs = [449] * len(volumes)

    ax.loglog(volumes, lambda_costs, linewidth=3, label="Lambda", color="#FF6B6B", marker="o", markersize=4)
    ax.loglog(volumes, keda_costs, linewidth=3, label="KEDA (1 node spot)", color="#4ECDC4", linestyle="--")

    ax.set_xlabel("Invocations per Month (log scale)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Annual Cost $ (log scale)", fontsize=12, fontweight="bold")
    ax.set_title("Break-Even Analysis: Lambda vs KEDA", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Annotate break-even
    ax.annotate("Break-even: ~5M/month", xy=(5_000_000, 450), xytext=(1_000_000, 1000),
                arrowprops=dict(arrowstyle="->", color="green", lw=2),
                fontsize=11, fontweight="bold", color="green")

    plt.tight_layout()
    plt.savefig("../results/graph_8_breakeven_volume.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_8_breakeven_volume.png")
    plt.close()

def graph_prewarming_effect():
    """Graph prewarming effect on latency."""
    fig, ax = plt.subplots(figsize=(12, 6))

    scenarios = ["Cold Start\n(first run,\nimage pull)", "Warm Start\n(image cached\non node)", "Prewarmed\n(DaemonSet\npre-pull)"]
    latencies = [4.5, 3.3, 2.3]
    colors = ["#FF6B6B", "#FFA07A", "#4ECDC4"]

    bars = ax.bar(scenarios, latencies, color=colors, edgecolor="black", linewidth=2, width=0.6)

    ax.set_ylabel("Latency (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("Prewarming Effect: Node Image Caching Reduces Cold Start", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 5)

    # Add value labels and improvement %
    for i, (bar, latency) in enumerate(zip(bars, latencies)):
        ax.text(bar.get_x() + bar.get_width()/2, latency + 0.1, f"{latency:.1f}s",
                ha="center", fontweight="bold", fontsize=12)

        if i == 0:
            ax.text(bar.get_x() + bar.get_width()/2, latency - 0.5, "Baseline", ha="center", fontweight="bold")
        elif i == 1:
            improvement = ((latencies[0] - latency) / latencies[0]) * 100
            ax.text(bar.get_x() + bar.get_width()/2, latency - 0.5, f"-{improvement:.0f}%",
                    ha="center", fontweight="bold", color="green")
        else:
            improvement = ((latencies[0] - latency) / latencies[0]) * 100
            ax.text(bar.get_x() + bar.get_width()/2, latency - 0.5, f"-{improvement:.0f}%",
                    ha="center", fontweight="bold", color="green")

    # Lambda baseline
    ax.axhline(y=0.2, color="red", linestyle="--", linewidth=2, label="Lambda (0.2s)")
    ax.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig("../results/graph_9_prewarming_effect.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_9_prewarming_effect.png")
    plt.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GENERATING SCALE ANALYSIS GRAPHS")
    print("="*60 + "\n")

    graph_scale_costs()
    graph_latency_comparison()
    graph_breakeven_volume()
    graph_prewarming_effect()

    print("\n✅ All graphs generated!")
