#!/usr/bin/env python3
"""
KEDA vs Lambda cost model — Part 2 with ARM64 pricing.
Adds Graviton3-based EKS nodes for comparison.
"""

import json
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum

class NodeType(Enum):
    X86_ON_DEMAND = ("m7i.xlarge", 0.1712)  # $/hr on-demand
    X86_SPOT = ("m7i.xlarge", 0.0512)       # $/hr spot (70% discount)
    ARM_ON_DEMAND = ("m7g.xlarge", 0.1088)  # Graviton3 on-demand
    ARM_SPOT = ("m7g.xlarge", 0.0326)       # Graviton3 spot (70% discount)

@dataclass
class CostScenario:
    name: str
    invocations_per_month: int
    avg_duration_ms: int
    memory_mb: int

def lambda_cost(scenario: CostScenario) -> Dict:
    """Calculate AWS Lambda pricing."""
    # AWS Lambda pricing (us-east-1)
    invocation_price = 0.0000002  # per invocation
    gb_second_price = 0.0000166667  # per GB-second

    # Calculate GB-seconds
    gb_seconds = (scenario.invocations_per_month *
                  scenario.avg_duration_ms / 1000 *
                  scenario.memory_mb / 1024)

    # Free tier: 1M invocations + 400K GB-seconds per month
    free_invocations = min(1_000_000, scenario.invocations_per_month)
    billable_invocations = scenario.invocations_per_month - free_invocations

    free_gb_seconds = min(400_000, gb_seconds)
    billable_gb_seconds = gb_seconds - free_gb_seconds

    cost = (billable_invocations * invocation_price +
            max(0, billable_gb_seconds) * gb_second_price)

    return {
        "invocation_cost": billable_invocations * invocation_price,
        "compute_cost": max(0, billable_gb_seconds) * gb_second_price,
        "total_monthly": cost,
        "total_annual": cost * 12
    }

def keda_cost(scenario: CostScenario, node_type: NodeType, node_count: int = 1, uptime_pct: float = 0.5) -> Dict:
    """Calculate KEDA on Kubernetes cost."""
    # Node hourly cost
    node_name, hourly_rate = node_type.value

    # Total node costs (running 24/7)
    monthly_hours = 730  # 24 * 30.4
    node_cost = node_count * hourly_rate * monthly_hours

    # EKS management fee (if applicable)
    eks_fee = 73  # $0.10/hour = ~$73/month (optional)

    # Data transfer (minimal for SQS/SNS)
    data_cost = 0

    total_monthly = node_cost + data_cost

    return {
        "node_cost": node_cost,
        "eks_fee": eks_fee,
        "data_cost": data_cost,
        "total_monthly": total_monthly,
        "total_annual": total_monthly * 12,
        "node_type": node_name,
        "node_count": node_count
    }

def cost_comparison(scenario: CostScenario) -> Dict:
    """Compare Lambda vs different KEDA configurations."""
    lambda_cost_result = lambda_cost(scenario)

    # KEDA scenarios
    keda_x86_single = keda_cost(scenario, NodeType.X86_SPOT, node_count=1)
    keda_x86_multi = keda_cost(scenario, NodeType.X86_SPOT, node_count=2)
    keda_arm_single = keda_cost(scenario, NodeType.ARM_SPOT, node_count=1)
    keda_arm_multi = keda_cost(scenario, NodeType.ARM_SPOT, node_count=2)

    return {
        "scenario": scenario.name,
        "invocations": scenario.invocations_per_month,
        "lambda": lambda_cost_result,
        "keda": {
            "x86_single_node": keda_x86_single,
            "x86_multi_node": keda_x86_multi,
            "arm_single_node": keda_arm_single,
            "arm_multi_node": keda_arm_multi,
        },
        "savings": {
            "x86_single": lambda_cost_result["total_monthly"] - keda_x86_single["total_monthly"],
            "x86_multi": lambda_cost_result["total_monthly"] - keda_x86_multi["total_monthly"],
            "arm_single": lambda_cost_result["total_monthly"] - keda_arm_single["total_monthly"],
            "arm_multi": lambda_cost_result["total_monthly"] - keda_arm_multi["total_monthly"],
        }
    }

def print_comparison(comp: Dict):
    """Pretty-print cost comparison."""
    print(f"\n{'=' * 80}")
    print(f"Scenario: {comp['scenario']} ({comp['invocations']:,} invocations/month)")
    print(f"{'=' * 80}\n")

    lambda_result = comp["lambda"]
    print(f"AWS Lambda:")
    print(f"  Invocation cost: ${lambda_result['invocation_cost']:,.2f}")
    print(f"  Compute cost (GB-seconds): ${lambda_result['compute_cost']:,.2f}")
    print(f"  Monthly: ${lambda_result['total_monthly']:,.2f}")
    print(f"  Annual: ${lambda_result['total_annual']:,.2f}\n")

    keda = comp["keda"]
    savings = comp["savings"]

    print(f"KEDA on EKS (x86 / m7i.xlarge):")
    print(f"  Single node (spot): ${keda['x86_single_node']['total_monthly']:,.2f}/mo (saves ${savings['x86_single']:,.2f})")
    print(f"  Multi-node (spot): ${keda['x86_multi_node']['total_monthly']:,.2f}/mo (saves ${savings['x86_multi']:,.2f})\n")

    print(f"KEDA on EKS (ARM / m7g.xlarge + Graviton3):")
    print(f"  Single node (spot): ${keda['arm_single_node']['total_monthly']:,.2f}/mo (saves ${savings['arm_single']:,.2f})")
    print(f"  Multi-node (spot): ${keda['arm_multi_node']['total_monthly']:,.2f}/mo (saves ${savings['arm_multi']:,.2f})\n")

    # ARM advantage
    x86_cost = keda['x86_single_node']['total_monthly']
    arm_cost = keda['arm_single_node']['total_monthly']
    arm_savings = x86_cost - arm_cost
    arm_pct = (arm_savings / x86_cost * 100) if x86_cost > 0 else 0
    print(f"ARM vs x86 savings: ${arm_savings:,.2f}/mo ({arm_pct:.1f}% cheaper)")
    print()

if __name__ == "__main__":
    # Define scenarios
    scenarios = [
        CostScenario("Dev/Test", 10_000, 500, 256),
        CostScenario("Small Production", 100_000, 800, 512),
        CostScenario("Medium Production", 1_000_000, 1000, 1024),
        CostScenario("Large Production", 10_000_000, 1500, 2048),
    ]

    print("\n🔬 KEDA vs Lambda Cost Analysis (with ARM64 pricing)")
    print("=" * 80)

    results = []
    for scenario in scenarios:
        comp = cost_comparison(scenario)
        print_comparison(comp)
        results.append(comp)

    # Break-even analysis
    print("\n" + "=" * 80)
    print("Break-Even Analysis (KEDA vs Lambda)")
    print("=" * 80)
    print("\nAt what volume does KEDA become cheaper?\n")

    for invocations in [10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000, 10_000_000]:
        scenario = CostScenario("Break-even test", invocations, 1000, 512)
        lambda_cost_result = lambda_cost(scenario)
        keda_result = keda_cost(scenario, NodeType.ARM_SPOT, node_count=1)

        if lambda_cost_result["total_monthly"] > keda_result["total_monthly"]:
            break_even = "✓ KEDA cheaper"
            savings = lambda_cost_result["total_monthly"] - keda_result["total_monthly"]
            print(f"  {invocations:>10,} invocations/mo: ${lambda_cost_result['total_monthly']:>7,.0f} Lambda vs ${keda_result['total_monthly']:>7,.0f} KEDA — {break_even} (save ${savings:,.0f})")
        else:
            print(f"  {invocations:>10,} invocations/mo: ${lambda_cost_result['total_monthly']:>7,.0f} Lambda vs ${keda_result['total_monthly']:>7,.0f} KEDA — Lambda cheaper")

    # JSON output
    print("\n\nJSON output:")
    print(json.dumps(results, indent=2))
