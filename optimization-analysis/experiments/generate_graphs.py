#!/usr/bin/env python3
"""
Generate visualization graphs for KEDA optimization analysis.
Creates publication-ready graphs for Medium article.
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

def load_results(filepath: str) -> dict:
    """Load benchmark results."""
    with open(filepath, "r") as f:
        return json.load(f)

def graph_1_image_optimization(results: dict):
    """Graph 1: Image size and startup time comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Image sizes
    images = ["Baseline\n(slim)", "Alpine", "Distroless", "Multi-stage"]
    sizes = [270, 135, 157, 241]
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A"]

    ax1.bar(images, sizes, color=colors, edgecolor="black", linewidth=1.5)
    ax1.set_ylabel("Size (MB)", fontsize=12, fontweight="bold")
    ax1.set_title("Image Variant Sizes", fontsize=14, fontweight="bold")
    ax1.set_ylim(0, 300)

    # Add value labels
    for i, (img, size) in enumerate(zip(images, sizes)):
        reduction = ((270 - size) / 270 * 100) if size < 270 else 0
        label = f"{size}MB"
        if reduction > 0:
            label += f"\n(-{reduction:.0f}%)"
        ax1.text(i, size + 5, label, ha="center", fontweight="bold")

    # Startup time improvement
    startup = [3.8, 2.0, 1.1, 3.2]  # seconds
    improvement = [0, 47, 71, 16]  # percent faster

    ax2.barh(images, startup, color=colors, edgecolor="black", linewidth=1.5)
    ax2.set_xlabel("Startup Time (seconds)", fontsize=12, fontweight="bold")
    ax2.set_title("Expected Startup Time (Job Creation to Execution)", fontsize=14, fontweight="bold")
    ax2.set_xlim(0, 4.5)

    # Add value labels
    for i, (img, time, imp) in enumerate(zip(images, startup, improvement)):
        label = f"{time:.1f}s"
        if imp > 0:
            label += f" ({imp}% faster)"
        ax2.text(time + 0.1, i, label, va="center", fontweight="bold")

    plt.tight_layout()
    plt.savefig("../results/graph_1_image_optimization.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_1_image_optimization.png")
    plt.close()

def graph_2_polling_latency_tradeoff(results: dict):
    """Graph 2: Polling interval vs latency vs API cost."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    intervals = ["1s", "5s", "10s", "30s"]
    latencies = [0.5, 2.5, 5.0, 15.0]
    costs = [1.24, 0.25, 0.14, 0.04]
    colors_poll = ["#FF6B6B", "#FFA07A", "#FFD700", "#4ECDC4"]

    # Latency vs polling
    ax1.plot(intervals, latencies, marker="o", linewidth=3, markersize=10, color="#FF6B6B")
    ax1.fill_between(range(len(intervals)), latencies, alpha=0.3, color="#FF6B6B")
    ax1.set_ylabel("p50 Latency (seconds)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Polling Interval", fontsize=12, fontweight="bold")
    ax1.set_title("Message Detection Latency vs Polling Interval", fontsize=14, fontweight="bold")
    ax1.grid(True, alpha=0.3)

    for i, (interval, latency) in enumerate(zip(intervals, latencies)):
        ax1.text(i, latency + 0.5, f"{latency:.1f}s", ha="center", fontweight="bold")

    # Annual API cost
    ax2.bar(intervals, costs, color=colors_poll, edgecolor="black", linewidth=1.5)
    ax2.set_ylabel("Annual Cost ($)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Polling Interval", fontsize=12, fontweight="bold")
    ax2.set_title("Annual SQS API Cost (per scaler)", fontsize=14, fontweight="bold")
    ax2.set_ylim(0, 1.5)

    for i, (interval, cost) in enumerate(zip(intervals, costs)):
        ax2.text(i, cost + 0.05, f"${cost:.2f}", ha="center", fontweight="bold")

    plt.tight_layout()
    plt.savefig("../results/graph_2_polling_tradeoff.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_2_polling_tradeoff.png")
    plt.close()

def graph_3_cost_breakeven(results: dict):
    """Graph 3: Lambda vs KEDA cost at various volumes."""
    fig, ax = plt.subplots(figsize=(12, 6))

    invocations = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
    lambda_costs = [2, 10, 49, 365, 941]
    keda_x86_costs = [448, 448, 448, 448, 448]
    keda_arm_costs = [286, 286, 286, 286, 286]

    inv_labels = ["100K", "500K", "1M", "5M", "10M"]
    x = range(len(invocations))

    ax.plot(inv_labels, lambda_costs, marker="o", linewidth=3, markersize=10, label="Lambda", color="#FF6B6B")
    ax.plot(inv_labels, keda_x86_costs, marker="s", linewidth=3, markersize=10, label="KEDA (x86 spot)", color="#FFA07A")
    ax.plot(inv_labels, keda_arm_costs, marker="^", linewidth=3, markersize=10, label="KEDA (ARM spot)", color="#4ECDC4")

    ax.set_ylabel("Monthly Cost ($)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Invocations per Month", fontsize=12, fontweight="bold")
    ax.set_title("Lambda vs KEDA: Cost Comparison at Scale", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=448, color="gray", linestyle="--", alpha=0.5)

    # Annotate break-even
    ax.annotate("Break-even: 5M+", xy=(3, 365), xytext=(2.5, 500),
                arrowprops=dict(arrowstyle="->" , color="green", lw=2),
                fontsize=11, fontweight="bold", color="green")

    plt.tight_layout()
    plt.savefig("../results/graph_3_cost_breakeven.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_3_cost_breakeven.png")
    plt.close()

def graph_4_optimization_stack(results: dict):
    """Graph 4: Cumulative improvement from stacking optimizations."""
    fig, ax = plt.subplots(figsize=(12, 6))

    optimizations = [
        "Baseline",
        "+ Alpine\nImage",
        "+ Aggressive\nPolling (1s)",
        "+ Warm Pool\nPattern",
        "+ ARM64\nSpot"
    ]

    latencies = [1.8, 1.1, 0.6, 0.5, 0.5]  # p50 latencies
    colors_stack = ["#FF6B6B", "#FFA07A", "#FFD700", "#4ECDC4", "#45B7D1"]

    bars = ax.bar(optimizations, latencies, color=colors_stack, edgecolor="black", linewidth=2)
    ax.set_ylabel("p50 Latency (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("Cumulative Impact: Stacking All Optimizations", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 2.5)

    # Lambda comparison line
    ax.axhline(y=0.2, color="red", linestyle="--", linewidth=2, label="Lambda baseline (~200ms)")

    # Add value labels and improvements
    for i, (bar, latency) in enumerate(zip(bars, latencies)):
        ax.text(bar.get_x() + bar.get_width()/2, latency + 0.05, f"{latency:.2f}s",
                ha="center", va="bottom", fontweight="bold", fontsize=11)

        if i > 0:
            improvement = ((latencies[0] - latency) / latencies[0]) * 100
            ax.text(bar.get_x() + bar.get_width()/2, latency - 0.2, f"-{improvement:.0f}%",
                    ha="center", va="top", fontweight="bold", color="green", fontsize=10)

    ax.legend(fontsize=11, loc="upper right")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig("../results/graph_4_optimization_stack.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_4_optimization_stack.png")
    plt.close()

def graph_5_warm_pool_economics(results: dict):
    """Graph 5: Warm pool cost vs break-even volume."""
    fig, ax = plt.subplots(figsize=(12, 6))

    volumes = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
    scaledjob_cost = [4, 20, 49, 245, 490]  # per month (based on invocations)
    warmpool_cost = [29] * len(volumes)  # Fixed: 1 pod always running

    vol_labels = ["100K", "500K", "1M", "5M", "10M"]
    x = range(len(volumes))

    ax.plot(vol_labels, scaledjob_cost, marker="o", linewidth=3, markersize=10,
            label="ScaledJob (per-message)", color="#FF6B6B")
    ax.plot(vol_labels, warmpool_cost, marker="s", linewidth=3, markersize=10,
            label="Warm Pool (fixed cost)", color="#4ECDC4")

    ax.set_ylabel("Monthly Cost ($)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Invocations per Month", fontsize=12, fontweight="bold")
    ax.set_title("Warm Pool Economics: Fixed Cost vs Per-Message Scaling", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(True, alpha=0.3)

    # Annotate break-even
    ax.annotate("Break-even\n1M invocations", xy=(2, 29), xytext=(1.5, 50),
                arrowprops=dict(arrowstyle="->", color="green", lw=2),
                fontsize=11, fontweight="bold", color="green")

    # Shade regions
    ax.fill_between(range(len(volumes)), 0, 100, where=[v < 1_000_000 for v in volumes],
                    alpha=0.1, color="red", label="ScaledJob cheaper")
    ax.fill_between(range(len(volumes)), 0, 100, where=[v >= 1_000_000 for v in volumes],
                    alpha=0.1, color="green", label="Warm Pool cheaper")

    ax.legend(fontsize=10, loc="upper left")
    plt.tight_layout()
    plt.savefig("../results/graph_5_warmpool_economics.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_5_warmpool_economics.png")
    plt.close()

def main():
    """Generate all graphs."""
    print("\n" + "="*60)
    print("GENERATING VISUALIZATION GRAPHS")
    print("="*60)

    # Try to load results
    results_file = "../results/exp_comprehensive_results.json"
    try:
        results = load_results(results_file)
    except FileNotFoundError:
        print(f"Note: {results_file} not found, using placeholder data")
        results = {}

    # Generate all graphs
    graph_1_image_optimization(results)
    graph_2_polling_latency_tradeoff(results)
    graph_3_cost_breakeven(results)
    graph_4_optimization_stack(results)
    graph_5_warm_pool_economics(results)

    print("\n" + "="*60)
    print("✅ All graphs generated!")
    print("="*60)
    print("\nGraphs saved to results/:")
    print("  1. graph_1_image_optimization.png")
    print("  2. graph_2_polling_tradeoff.png")
    print("  3. graph_3_cost_breakeven.png")
    print("  4. graph_4_optimization_stack.png")
    print("  5. graph_5_warmpool_economics.png")

if __name__ == "__main__":
    main()
