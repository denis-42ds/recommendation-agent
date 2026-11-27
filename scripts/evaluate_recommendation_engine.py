from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from recommendation_agent.data_loader import load_recommendation_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate recommendation engine coverage and Fill Rate."
    )
    parser.add_argument(
        "workbook",
        type=Path,
        help="Path to the source Excel workbook.",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("artifacts/product_graph/graph.json"),
    )
    parser.add_argument(
        "--matched-products",
        type=Path,
        default=Path("artifacts/catalog/matched_products.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to save the JSON report.",
    )
    return parser.parse_args()


def new_bucket() -> dict[str, Any]:
    return {
        "clients": 0,
        "clients_with_recommendations": 0,
        "clients_with_top3": 0,
        "recommendation_count": 0,
        "available_slots": 0,
        "reason_counts": Counter(),
    }


def update_bucket(
    bucket: dict[str, Any],
    recommendations: list[Any],
    k: int,
) -> None:
    count = len(recommendations)

    bucket["clients"] += 1
    bucket["recommendation_count"] += count
    bucket["available_slots"] += k

    if count:
        bucket["clients_with_recommendations"] += 1

    if count == k:
        bucket["clients_with_top3"] += 1

    for recommendation in recommendations:
        for reason in recommendation.reason_codes:
            bucket["reason_counts"][reason] += 1


def finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    clients = bucket["clients"]
    slots = bucket["available_slots"]

    return {
        "clients": clients,
        "clients_with_recommendations": bucket[
            "clients_with_recommendations"
        ],
        "clients_with_top3": bucket["clients_with_top3"],
        "recommendation_count": bucket["recommendation_count"],
        "mean_recommendations_per_client": (
            round(bucket["recommendation_count"] / clients, 4)
            if clients else 0.0
        ),
        "fill_rate": (
            round(bucket["recommendation_count"] / slots, 4)
            if slots else 0.0
        ),
        "clients_with_any_recommendation_rate": (
            round(bucket["clients_with_recommendations"] / clients, 4)
            if clients else 0.0
        ),
        "top3_rate": (
            round(bucket["clients_with_top3"] / clients, 4)
            if clients else 0.0
        ),
        "reason_counts": dict(sorted(bucket["reason_counts"].items())),
    }


def main() -> None:
    args = parse_args()

    data = load_recommendation_data(
        workbook_path=args.workbook,
        graph_path=args.graph,
        matched_products_path=args.matched_products,
    )

    k = 3
    buckets: dict[str, dict[str, Any]] = defaultdict(new_bucket)
    reason_totals: Counter[str] = Counter()
    unsupported_groups: Counter[str] = Counter()

    total_clients = len(data.client_groups)
    clients_with_history = sum(
        bool(data.histories.get(client_id))
        for client_id in data.client_groups
    )

    for client_id, client_group in sorted(data.client_groups.items()):
        group = str(client_group).strip().upper()

        if group not in {"B2B", "B2C"}:
            unsupported_groups[group or "<EMPTY>"] += 1
            continue

        history = data.histories.get(client_id, set())
        history_type = "with_history" if history else "cold_start"

        result = data.engine.recommend(
            history_item_ids=history,
            client_group=group,
            k=k,
        )

        recommendations = list(result.recommendations)

        update_bucket(buckets["ALL"], recommendations, k)
        update_bucket(buckets[group], recommendations, k)
        update_bucket(buckets[history_type], recommendations, k)
        update_bucket(
            buckets[f"{group}_{history_type}"],
            recommendations,
            k,
        )

        for recommendation in recommendations:
            reason_totals.update(recommendation.reason_codes)

    report = {
        "configuration": {
            "k": k,
            "workbook": str(args.workbook),
            "graph": str(args.graph),
            "matched_products": str(args.matched_products),
        },
        "dataset": {
            "total_clients": total_clients,
            "clients_with_history": clients_with_history,
            "clients_without_history": total_clients - clients_with_history,
            "unsupported_group_clients": sum(unsupported_groups.values()),
            "evaluated_clients": buckets["ALL"]["clients"],
        },
        "metrics": {
            name: finalize_bucket(bucket)
            for name, bucket in sorted(buckets.items())
        },
        "recommendation_reason_totals": dict(
            sorted(reason_totals.items())
        ),
        "unsupported_groups": dict(sorted(unsupported_groups.items())),
    }

    output = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )

    print(output)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
