#!/usr/bin/env python3
"""Generate publication-quality statistical graphs."""

import json
import matplotlib.pyplot as plt
import numpy as np

def load_results(filepath: str = "../results/statistical_results.json") -> dict:
    """Load experiment results."""
    with open(filepath, "r") as f:
        return json.load(f)

def graph_boxplot_all_patterns(results: dict):
    """Box plot showing distribution across all patterns."""
    fig, ax = plt.subplots(figsize=(14, 6))

    patterns = []
    data = []

    for pattern_name, stats in sorted(results["patterns"].items(), key=lambda x: x[1]["median"]):
        patterns.append(pattern_name)
        data.append(stats["raw_values"])

    bp = ax.boxplot(data, labels=patterns, patch_artist=True)

    # Color boxes
    colors = ["#FF6B6B", "#FFA07A", "#FFD700", "#4ECDC4", "#45B7D1", "#95E1D3"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)

    ax.set_ylabel("Latency (ms)", fontsize=12, fontweight="bold")
    ax.set_title("Latency Distribution: Box Plot of 10 Trials per Pattern", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    plt.savefig("../results/graph_10_boxplot_distributions.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_10_boxplot_distributions.png")
    plt.close()

def graph_percentiles_comparison(results: dict):
    """Line graph showing p50, p95, p99 percentiles."""
    fig, ax = plt.subplots(figsize=(14, 6))

    patterns = sorted(results["patterns"].keys(), key=lambda p: results["patterns"][p]["median"])
    p50_values = [results["patterns"][p]["p50"] for p in patterns]
    p95_values = [results["patterns"][p]["p95"] for p in patterns]
    p99_values = [results["patterns"][p]["p99"] for p in patterns]

    x = np.arange(len(patterns))
    width = 0.25

    ax.bar(x - width, p50_values, width, label="p50 (median)", color="#4ECDC4")
    ax.bar(x, p95_values, width, label="p95", color="#FFA07A")
    ax.bar(x + width, p99_values, width, label="p99 (worst case)", color="#FF6B6B")

    ax.set_ylabel("Latency (ms)", fontsize=12, fontweight="bold")
    ax.set_title("Percentile Performance: p50, p95, p99 Latencies", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(patterns, rotation=15, ha="right")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig("../results/graph_11_percentile_comparison.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_11_percentile_comparison.png")
    plt.close()

def graph_variability_consistency(results: dict):
    """Scatter plot: latency vs variability."""
    fig, ax = plt.subplots(figsize=(12, 6))

    patterns = list(results["patterns"].keys())
    latencies = [results["patterns"][p]["median"] for p in patterns]
    std_devs = [results["patterns"][p]["stdev"] for p in patterns]
    colors_list = ["#FF6B6B", "#FFA07A", "#FFD700", "#4ECDC4", "#45B7D1", "#95E1D3"]

    for i, (pattern, lat, std) in enumerate(zip(patterns, latencies, std_devs)):
        ax.scatter(lat, std, s=400, alpha=0.6, color=colors_list[i], edgecolor="black", linewidth=2)
        ax.annotate(pattern, (lat, std), xytext=(10, 10), textcoords="offset points", fontsize=9, fontweight="bold")

    ax.set_xlabel("Median Latency (ms)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Standard Deviation (ms)", fontsize=12, fontweight="bold")
    ax.set_title("Consistency Analysis: Latency vs Variability", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Add quadrant lines
    ax.axhline(y=400, color="gray", linestyle="--", alpha=0.3)
    ax.axvline(x=2500, color="gray", linestyle="--", alpha=0.3)

    # Annotate quadrants
    ax.text(1500, 450, "Fast + Consistent\n(Best)", ha="center", fontsize=10, fontweight="bold", color="green", alpha=0.5)
    ax.text(4000, 450, "Slow + Consistent\n(Acceptable)", ha="center", fontsize=10, fontweight="bold", color="orange", alpha=0.5)
    ax.text(1500, 100, "Fast + Unpredictable\n(Risky)", ha="center", fontsize=10, fontweight="bold", color="orange", alpha=0.5)
    ax.text(4000, 100, "Slow + Unpredictable\n(Bad)", ha="center", fontsize=10, fontweight="bold", color="red", alpha=0.5)

    plt.tight_layout()
    plt.savefig("../results/graph_12_consistency_analysis.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_12_consistency_analysis.png")
    plt.close()

def graph_violin_plot(results: dict):
    """Violin plot showing full distribution."""
    fig, ax = plt.subplots(figsize=(14, 6))

    patterns = sorted(results["patterns"].keys(), key=lambda p: results["patterns"][p]["median"])
    data = [results["patterns"][p]["raw_values"] for p in patterns]

    parts = ax.violinplot(data, positions=range(len(patterns)), widths=0.7, showmeans=True, showmedians=True)

    # Color the violins
    colors = ["#FF6B6B", "#FFA07A", "#FFD700", "#4ECDC4", "#45B7D1", "#95E1D3"]
    for pc, color in zip(parts["bodies"], colors):
        pc.set_facecolor(color)
        pc.set_alpha(0.7)

    ax.set_ylabel("Latency (ms)", fontsize=12, fontweight="bold")
    ax.set_title("Latency Distribution: Violin Plot (Full Distribution Density)", fontsize=14, fontweight="bold")
    ax.set_xticks(range(len(patterns)))
    ax.set_xticklabels(patterns, rotation=15, ha="right")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig("../results/graph_13_violin_distributions.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_13_violin_distributions.png")
    plt.close()

def graph_summary_table(results: dict):
    """Create a summary statistics table as image."""
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.axis("tight")
    ax.axis("off")

    # Prepare table data
    table_data = []
    header = ["Pattern", "Trials", "Min (ms)", "Max (ms)", "Mean (ms)", "Median (ms)", "Std Dev (ms)", "p95 (ms)", "p99 (ms)"]
    table_data.append(header)

    for pattern in sorted(results["patterns"].keys(), key=lambda p: results["patterns"][p]["median"]):
        stats = results["patterns"][pattern]
        row = [
            pattern,
            f"{stats['count']}",
            f"{stats['min']:.0f}",
            f"{stats['max']:.0f}",
            f"{stats['mean']:.0f}",
            f"{stats['median']:.0f}",
            f"{stats['stdev']:.0f}",
            f"{stats['p95']:.0f}",
            f"{stats['p99']:.0f}",
        ]
        table_data.append(row)

    table = ax.table(cellText=table_data, cellLoc="center", loc="center", colWidths=[0.18, 0.08, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header
    for i in range(len(header)):
        table[(0, i)].set_facecolor("#4ECDC4")
        table[(0, i)].set_text_props(weight="bold", color="white")

    # Alternate row colors
    for i in range(1, len(table_data)):
        color = "#F0F0F0" if i % 2 == 0 else "white"
        for j in range(len(header)):
            table[(i, j)].set_facecolor(color)

    plt.title("Statistical Summary: 10 Trials per Pattern", fontsize=14, fontweight="bold", pad=20)
    plt.savefig("../results/graph_14_summary_table.png", dpi=300, bbox_inches="tight")
    print("✅ Saved: graph_14_summary_table.png")
    plt.close()

def main():
    print("\n" + "="*60)
    print("GENERATING STATISTICAL GRAPHS")
    print("="*60 + "\n")

    results = load_results()

    graph_boxplot_all_patterns(results)
    graph_percentiles_comparison(results)
    graph_variability_consistency(results)
    graph_violin_plot(results)
    graph_summary_table(results)

    print("\n✅ All statistical graphs generated!")
    print("\nGraphs for Medium publication:")
    print("  - graph_10_boxplot_distributions.png")
    print("  - graph_11_percentile_comparison.png")
    print("  - graph_12_consistency_analysis.png")
    print("  - graph_13_violin_distributions.png")
    print("  - graph_14_summary_table.png")

if __name__ == "__main__":
    main()
