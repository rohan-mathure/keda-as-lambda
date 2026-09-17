#!/usr/bin/env python3
"""
Cost analysis: AWS Lambda vs KEDA on K8s.

Compares total monthly cost across different invocation rates.
"""

import json
from typing import Dict, Tuple


class LambdaCostCalculator:
    """AWS Lambda pricing model."""

    # AWS Lambda pricing (as of 2024)
    PRICE_PER_INVOCATION = 0.0000002  # $0.20 per 1M invocations
    PRICE_PER_GB_SECOND = 0.0000166667  # $0.0000166667 per GB-second
    FREE_TIER_INVOCATIONS = 1_000_000  # per month
    FREE_TIER_GB_SECONDS = 400_000  # per month

    def __init__(self, memory_mb: int = 512, duration_ms: int = 500):
        """
        Initialize Lambda cost model.
        Args:
            memory_mb: Function memory (128-10240 MB)
            duration_ms: Average execution duration (ms)
        """
        self.memory_mb = memory_mb
        self.duration_ms = duration_ms
        self.memory_gb = memory_mb / 1024

    def monthly_cost(self, invocations: int) -> float:
        """Calculate total monthly cost for given invocation count."""
        # Skip free tier if over limits
        if invocations > self.FREE_TIER_INVOCATIONS:
            invocation_cost = (invocations - self.FREE_TIER_INVOCATIONS) * self.PRICE_PER_INVOCATION
        else:
            invocation_cost = 0

        gb_seconds = invocations * (self.duration_ms / 1000) * self.memory_gb
        if gb_seconds > self.FREE_TIER_GB_SECONDS:
            compute_cost = (gb_seconds - self.FREE_TIER_GB_SECONDS) * self.PRICE_PER_GB_SECOND
        else:
            compute_cost = 0

        return invocation_cost + compute_cost


class KedaCostCalculator:
    """Kubernetes (KEDA) cost model."""

    # AWS EKS pricing
    EKS_CLUSTER_COST = 0.10  # per hour
    EKS_CLUSTER_COST_MONTHLY = EKS_CLUSTER_COST * 730

    # Node instance costs (on-demand EC2 t3.medium in us-east-1, ~2024 pricing)
    NODE_HOURLY_COST = 0.0416  # t3.medium
    NODE_MONTHLY_COST = NODE_HOURLY_COST * 730  # per node

    # Spot instance discount
    SPOT_DISCOUNT = 0.70  # ~70% cheaper with spot

    def __init__(
        self,
        node_count: int = 2,
        use_spot: bool = True,
        include_eks_cost: bool = True
    ):
        """
        Initialize Kubernetes cost model.
        Args:
            node_count: Number of cluster nodes
            use_spot: Use spot instances (70% discount)
            include_eks_cost: Include EKS management fee ($0.10/hr)
        """
        self.node_count = node_count
        self.use_spot = use_spot
        self.include_eks_cost = include_eks_cost

    def monthly_cost(self, _invocations: int = 0) -> float:
        """
        Calculate total monthly cost (fixed infrastructure cost).
        Args:
            _invocations: Unused (cost is fixed regardless of load)
        Returns: Monthly cost
        """
        node_cost = self.node_count * self.NODE_MONTHLY_COST
        if self.use_spot:
            node_cost *= (1 - self.SPOT_DISCOUNT)

        eks_cost = self.EKS_CLUSTER_COST_MONTHLY if self.include_eks_cost else 0

        return node_cost + eks_cost


def compare_costs(
    invocation_rates: list,
    lambda_config: Dict,
    keda_config: Dict
) -> Dict:
    """
    Compare Lambda vs KEDA costs across invocation rates.
    Returns dict with per-rate costs and break-even analysis.
    """
    lambda_calc = LambdaCostCalculator(**lambda_config)
    keda_calc = KedaCostCalculator(**keda_config)

    results = {
        "config": {
            "lambda": lambda_config,
            "keda": keda_config
        },
        "comparison": []
    }

    for rate in invocation_rates:
        lambda_cost = lambda_calc.monthly_cost(rate)
        keda_cost = keda_calc.monthly_cost(rate)
        delta = lambda_cost - keda_cost
        savings_pct = (delta / lambda_cost * 100) if lambda_cost > 0 else 0

        results["comparison"].append({
            "invocations": rate,
            "lambda_cost": round(lambda_cost, 2),
            "keda_cost": round(keda_cost, 2),
            "delta": round(delta, 2),
            "savings_pct": round(savings_pct, 1),
            "cheaper": "KEDA" if delta > 0 else "Lambda"
        })

    # Find break-even point
    results["break_even"] = _find_breakeven(lambda_calc, keda_calc)

    return results


def _find_breakeven(lambda_calc, keda_calc) -> int:
    """Binary search to find invocation rate where costs equal."""
    low, high = 1, 100_000_000
    while low < high:
        mid = (low + high) // 2
        if lambda_calc.monthly_cost(mid) < keda_calc.monthly_cost(mid):
            low = mid + 1
        else:
            high = mid
    return low


def print_report(results: Dict):
    """Pretty-print cost comparison report."""
    print("\n" + "=" * 100)
    print("KEDA-as-Lambda Cost Analysis".center(100))
    print("=" * 100)

    print("\n📋 Configuration:")
    print(f"  Lambda: {results['config']['lambda']['memory_mb']}MB, "
          f"{results['config']['lambda']['duration_ms']}ms avg duration")
    keda_conf = results['config']['keda']
    spot_str = "with Spot (70% discount)" if keda_conf['use_spot'] else "on-demand"
    eks_str = "including EKS mgmt ($0.10/hr)" if keda_conf['include_eks_cost'] else "excluding EKS"
    print(f"  KEDA: {keda_conf['node_count']} nodes {spot_str}, {eks_str}")

    print("\n💰 Cost Comparison (Monthly):")
    print("-" * 100)
    print(f"{'Invocations':>15} | {'Lambda Cost':>15} | {'KEDA Cost':>15} | {'Savings':>15} | {'Cheaper':>12}")
    print("-" * 100)

    for row in results['comparison']:
        inv = row['invocations']
        if inv >= 1_000_000:
            inv_str = f"{inv / 1_000_000:.0f}M"
        elif inv >= 1_000:
            inv_str = f"{inv / 1_000:.0f}K"
        else:
            inv_str = str(inv)

        lambda_str = f"${row['lambda_cost']:>14.2f}"
        keda_str = f"${row['keda_cost']:>14.2f}"
        delta_str = f"${row['delta']:>14.2f} ({row['savings_pct']:>5.1f}%)"
        cheaper = row['cheaper']

        print(f"{inv_str:>15} | {lambda_str} | {keda_str} | {delta_str} | {cheaper:>12}")

    print("-" * 100)

    breakeven = results['break_even']
    if breakeven >= 1_000_000:
        breakeven_str = f"{breakeven / 1_000_000:.1f}M invocations/month"
    else:
        breakeven_str = f"{breakeven:,} invocations/month"

    print(f"\n🔄 Break-even Point: {breakeven_str}")
    print("   (Above this rate, Lambda becomes cheaper; below, KEDA is cheaper)")

    print("\n✅ Pros & Cons:")
    print("\nKEDA on K8s:")
    print("  ✓ Fixed infrastructure cost (predictable)")
    print("  ✓ 70% discount with spot instances")
    print("  ✓ No runtime, memory, or timeout limits")
    print("  ✓ Same governance as existing K8s workloads")
    print("  ✓ Can share cluster capacity with other services")
    print("  ✗ Higher cold start (~1-3s pod scheduling)")
    print("  ✗ Operational overhead (own the cluster)")
    print("  ✗ No free tier")

    print("\nAWS Lambda:")
    print("  ✓ True serverless (no ops)")
    print("  ✓ 1M free invocations/month + 400k GB-seconds")
    print("  ✓ Fast cold start (~100-500ms)")
    print("  ✓ Simpler for low-volume workloads")
    print("  ✗ 15-minute timeout limit")
    print("  ✗ 10GB memory limit")
    print("  ✗ Higher cost at scale")
    print("  ✗ Vendor lock-in (AWS-specific APIs)")

    print("\n" + "=" * 100 + "\n")


def main():
    """Run cost analysis with example scenarios."""

    # Scenario 1: Small workload (development/testing)
    print("\n" + "🎯 Scenario 1: Small Workload (Dev/Test)" + "\n")
    results_small = compare_costs(
        invocation_rates=[100_000, 500_000, 1_000_000, 2_000_000],
        lambda_config={"memory_mb": 256, "duration_ms": 200},
        keda_config={"node_count": 1, "use_spot": True, "include_eks_cost": False}
    )
    print_report(results_small)

    # Scenario 2: Medium workload (production, mixed)
    print("\n" + "🎯 Scenario 2: Medium Workload (Production)" + "\n")
    results_medium = compare_costs(
        invocation_rates=[1_000_000, 5_000_000, 10_000_000, 50_000_000],
        lambda_config={"memory_mb": 512, "duration_ms": 500},
        keda_config={"node_count": 3, "use_spot": True, "include_eks_cost": True}
    )
    print_report(results_medium)

    # Scenario 3: High-volume workload
    print("\n" + "🎯 Scenario 3: High-Volume Workload" + "\n")
    results_high = compare_costs(
        invocation_rates=[10_000_000, 50_000_000, 100_000_000, 500_000_000],
        lambda_config={"memory_mb": 1024, "duration_ms": 1000},
        keda_config={"node_count": 10, "use_spot": True, "include_eks_cost": True}
    )
    print_report(results_high)

    # Save raw results for further analysis
    all_results = {
        "small": results_small,
        "medium": results_medium,
        "high": results_high
    }

    with open("analysis/cost_analysis_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("📊 Raw results saved to: analysis/cost_analysis_results.json")


if __name__ == '__main__':
    main()
