from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

TRAIN_END = pd.Timestamp("2026-08-31")
TOP_K = 3

OFFICIAL_PRECISION = {
    ("A", "ALL", "popularity"): 0.0544,
    ("A", "ALL", "co_purchase"): 0.0564,
    ("B", "ALL", "popularity"): 0.0736,
    ("B", "ALL", "co_purchase"): 0.0601,
}

REQUIRED_SALES_COLUMNS = {
    "order_id",
    "client_id",
    "order_week",
    "item_id",
}

REQUIRED_CLIENT_COLUMNS = {
    "client_id",
    "client_group",
}


def normalize_id(series: pd.Series) -> pd.Series:
    """Normalize identifiers without converting them to numeric values."""
    return series.astype("string").str.strip()


def load_data(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load sales and client reference data from the organizer workbook."""
    sales = pd.read_excel(
        path,
        sheet_name="Продажи",
        engine="openpyxl",
    )
    clients = pd.read_excel(
        path,
        sheet_name="Клиенты",
        engine="openpyxl",
    )

    missing_sales = REQUIRED_SALES_COLUMNS - set(sales.columns)
    missing_clients = REQUIRED_CLIENT_COLUMNS - set(clients.columns)

    if missing_sales:
        raise ValueError(f"В листе 'Продажи' отсутствуют колонки: {sorted(missing_sales)}")
    if missing_clients:
        raise ValueError(f"В листе 'Клиенты' отсутствуют колонки: {sorted(missing_clients)}")

    for column in ("order_id", "client_id", "item_id"):
        sales[column] = normalize_id(sales[column])

    clients["client_id"] = normalize_id(clients["client_id"])
    clients["client_group"] = normalize_id(clients["client_group"]).str.upper()

    sales["order_week"] = pd.to_datetime(sales["order_week"], errors="coerce")

    sales = sales.dropna(
        subset=["order_id", "client_id", "order_week", "item_id"]
    ).copy()

    clients = clients.dropna(subset=["client_id", "client_group"]).copy()
    clients = clients.drop_duplicates(subset=["client_id"], keep="last")

    return sales, clients


def split_train_test(
    sales: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the organizer's v4 date split."""
    train = sales[sales["order_week"] <= TRAIN_END].copy()
    test = sales[sales["order_week"] > TRAIN_END].copy()

    if train.empty:
        raise ValueError("Train пустой. Проверьте формат order_week.")
    if test.empty:
        raise ValueError("Test пустой. Проверьте формат order_week.")

    return train, test


def build_client_histories(
    train: pd.DataFrame,
) -> dict[str, set[str]]:
    """Return unique products bought by each client in train."""
    return (
        train.groupby("client_id")["item_id"]
        .apply(set)
        .to_dict()
    )


def build_test_targets(
    test: pd.DataFrame,
    histories: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Keep only new products bought by each client in test."""
    test_items = test.groupby("client_id")["item_id"].apply(set).to_dict()

    targets: dict[str, set[str]] = {}
    for client_id, items in test_items.items():
        known_items = histories.get(client_id, set())
        new_items = items - known_items
        if new_items:
            targets[client_id] = new_items

    return targets


def build_cohort(
    histories: dict[str, set[str]],
    targets: dict[str, set[str]],
    clients: pd.DataFrame,
) -> pd.DataFrame:
    """Build group A and cold-start group B from eligible clients."""
    client_groups = clients.set_index("client_id")["client_group"].to_dict()

    rows = []
    for client_id, target_items in targets.items():
        history = histories.get(client_id, set())

        # Group A requires a non-empty training history and a new test item.
        if not history or not target_items:
            continue

        rows.append(
            {
                "client_id": client_id,
                "client_group": client_groups.get(client_id, "UNKNOWN"),
                "history_size": len(history),
                "target_items": target_items,
                "cohort": "A",
            }
        )

    cohort = pd.DataFrame(rows)
    if cohort.empty:
        raise ValueError("Не удалось сформировать группу A.")

    cold_start = cohort[cohort["history_size"] == 1].copy()
    cold_start["cohort"] = "B"

    return pd.concat([cohort, cold_start], ignore_index=True)


def build_popularity_ranking(
    train: pd.DataFrame,
) -> tuple[list[str], dict[str, int]]:
    """
    Rank products by the number of distinct clients who bought them.

    Each client contributes at most one count per item.
    """
    client_items = train[["client_id", "item_id"]].drop_duplicates()

    counts = (
        client_items.groupby("item_id")["client_id"]
        .nunique()
        .to_dict()
    )

    ranking = sorted(
        counts,
        key=lambda item: (-counts[item], item),
    )

    return ranking, counts


def build_item_cooccurrence(
    train: pd.DataFrame,
) -> dict[str, Counter[str]]:
    """
    Build an undirected item-item graph from composite baskets.

    Basket identity is (order_id, order_week).
    Each unordered item pair contributes once per basket.
    """
    basket_items = (
        train.groupby(["order_id", "order_week"])["item_id"]
        .apply(lambda values: sorted(set(values)))
    )

    graph: dict[str, Counter[str]] = defaultdict(Counter)

    for items in basket_items:
        for item_a, item_b in combinations(items, 2):
            graph[item_a][item_b] += 1
            graph[item_b][item_a] += 1

    return graph


def recommend_popularity(
    history: set[str],
    popularity_counts: dict[str, int],
    k: int = TOP_K,
) -> list[str]:
    """Recommend unseen products ranked by popularity."""
    candidates = [
        item for item in popularity_counts
        if item not in history
    ]

    candidates.sort(
        key=lambda item: (-popularity_counts[item], item)
    )

    return candidates[:k]


def recommend_co_purchase(
    history: set[str],
    graph: dict[str, Counter[str]],
    popularity_counts: dict[str, int],
    k: int = TOP_K,
) -> list[str]:
    """
    Rank unseen products by summed co-purchase score.

    Tie-breaks: higher popularity, then ascending item_id.
    """
    scores: Counter[str] = Counter()

    for history_item in history:
        scores.update(graph.get(history_item, {}))

    candidates = [
        item for item in scores
        if item not in history
    ]

    candidates.sort(
        key=lambda item: (
            -scores[item],
            -popularity_counts.get(item, 0),
            item,
        )
    )

    return candidates[:k]


def evaluate_predictions(
    cohort: pd.DataFrame,
    histories: dict[str, set[str]],
    targets: dict[str, set[str]],
    popularity_ranking: list[str],
    cooccurrence_graph: dict[str, Counter[str]],
    popularity_counts: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate per-client predictions and aggregate metrics."""
    prediction_rows = []

    for row in cohort.itertuples(index=False):
        client_id = row.client_id
        history = histories[client_id]
        target_items = targets[client_id]

        methods = {
                "popularity": recommend_popularity(history, popularity_counts,),
                "co_purchase": recommend_co_purchase(
                    history,
                    cooccurrence_graph,
                    popularity_counts,
                    ),
                }

        for method, recommendations in methods.items():
            hits = len(set(recommendations[:TOP_K]) & target_items)

            prediction_rows.append(
                {
                    "client_id": client_id,
                    "client_group": row.client_group,
                    "cohort": row.cohort,
                    "method": method,
                    "history_size": len(history),
                    "target_count": len(target_items),
                    "recommendation_count": len(recommendations),
                    "recommendations": "|".join(recommendations),
                    "hits": hits,
                    "precision_at_3": hits / TOP_K,
                    "has_recommendation": bool(recommendations),
                }
            )

    predictions = pd.DataFrame(prediction_rows)

    metric_rows = []
    for (cohort_name, method), method_df in predictions.groupby(
        ["cohort", "method"]
    ):
        for segment in ("ALL", "B2B", "B2C"):
            if segment == "ALL":
                subset = method_df
            else:
                subset = method_df[method_df["client_group"] == segment]

            if subset.empty:
                continue

            metric_rows.append(
                {
                    "cohort": cohort_name,
                    "segment": segment,
                    "method": method,
                    "client_count": len(subset),
                    "precision_at_3": subset["precision_at_3"].mean(),
                    "fill_rate": subset["has_recommendation"].mean(),
                }
            )

    metrics = pd.DataFrame(metric_rows)
    return predictions, metrics


def save_cohort_sizes(cohort: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Save unique client counts for groups A and B."""
    sizes = (
        cohort.drop_duplicates(subset=["client_id", "cohort"])
        .groupby(["cohort", "client_group"])
        .size()
        .rename("client_count")
        .reset_index()
    )

    all_rows = (
        cohort.drop_duplicates(subset=["client_id", "cohort"])
        .groupby("cohort")
        .size()
        .rename("client_count")
        .reset_index()
    )
    all_rows["client_group"] = "ALL"

    sizes = pd.concat([sizes, all_rows], ignore_index=True)
    sizes.to_csv(output_dir / "cohort_sizes.csv", index=False)
    return sizes


def plot_metric(
    metrics: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    """Create a comparison chart for groups A and B."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    segments = ["ALL", "B2B", "B2C"]
    methods = ["popularity", "co_purchase"]
    labels = {
        "popularity": "Popularity",
        "co_purchase": "Co-purchase",
    }

    for axis, cohort_name in zip(axes, ["A", "B"], strict=True):
        subset = metrics[metrics["cohort"] == cohort_name]

        x_positions = list(range(len(segments)))
        width = 0.35

        for method_index, method in enumerate(methods):
            values = []
            for segment in segments:
                match = subset[
                    (subset["segment"] == segment)
                    & (subset["method"] == method)
                ]
                values.append(
                    float(match.iloc[0][metric]) if not match.empty else 0.0
                )

            offset = (method_index - 1) * width
            bars = axis.bar(
                [x + offset for x in x_positions],
                values,
                width,
                label=labels[method],
            )

            if metric == "precision_at_3":
                axis.bar_label(
                    bars,
                    labels=[f"{value:.1%}" for value in values],
                    padding=3,
                    fontsize=8,
                )

        if metric == "precision_at_3":
            official_values = [
                OFFICIAL_PRECISION.get(
                    (cohort_name, segment, "popularity"),
                    0.0,
                )
                for segment in segments
            ]

            official_bars = axis.bar(
                [x + width for x in x_positions],
                official_values,
                width,
                label="Organizer Popularity",
                hatch="//",
                fill=False,
            )

            axis.bar_label(
                official_bars,
                labels=[
                    f"{value:.2%}" if value > 0 else ""
                    for value in official_values
                ],
                padding=3,
                fontsize=8,
            )

        axis.set_title(f"Group {cohort_name}")
        axis.set_xticks(x_positions, segments)
        axis.set_ylim(0, 1)
        axis.grid(axis="y", alpha=0.25)
        axis.set_axisbelow(True)

    axes[0].set_ylabel(ylabel)
    axes[1].legend(loc="upper right")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_cohort_sizes(sizes: pd.DataFrame, output_path: Path) -> None:
    """Visualize the number of clients in groups A and B by segment."""
    subset = sizes[sizes["client_group"].isin(["B2B", "B2C"])]

    pivot = subset.pivot(
        index="client_group",
        columns="cohort",
        values="client_count",
    ).fillna(0)

    pivot = pivot.reindex(["B2B", "B2C"])

    ax = pivot.plot(
        kind="bar",
        figsize=(8, 5),
        rot=0,
    )
    ax.set_title("Evaluation cohort sizes")
    ax.set_xlabel("Client segment")
    ax.set_ylabel("Number of clients")
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate recommendation baselines on the organizer dataset."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("docs/source-materials/Датасет_Рекомендации_ЛК_v4.xlsx"),
        help="Path to the organizer Excel workbook.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/baseline"),
        help="Directory for CSV reports and charts.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Файл датасета не найден: {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)

    sales, clients = load_data(args.input)
    train, test = split_train_test(sales)

    histories = build_client_histories(train)
    targets = build_test_targets(test, histories)
    cohort = build_cohort(histories, targets, clients)

    popularity_ranking, popularity_counts = build_popularity_ranking(train)
    cooccurrence_graph = build_item_cooccurrence(train)

    predictions, metrics = evaluate_predictions(
        cohort=cohort,
        histories=histories,
        targets=targets,
        popularity_ranking=popularity_ranking,
        cooccurrence_graph=cooccurrence_graph,
        popularity_counts=popularity_counts,
    )

    sizes = save_cohort_sizes(cohort, args.output)

    predictions.to_csv(
        args.output / "predictions_by_client.csv",
        index=False,
    )
    metrics.to_csv(
        args.output / "baseline_metrics.csv",
        index=False,
    )

    plot_metric(
        metrics,
        metric="precision_at_3",
        title="Baseline comparison — Precision@3",
        ylabel="Precision@3",
        output_path=args.output / "precision_at_3.png",
    )
    plot_metric(
        metrics,
        metric="fill_rate",
        title="Baseline comparison — Fill Rate",
        ylabel="Fill Rate",
        output_path=args.output / "fill_rate.png",
    )
    plot_cohort_sizes(
        sizes,
        output_path=args.output / "cohort_sizes.png",
    )

    print("\nBaseline calculation completed.")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print("\nMetrics:")
    print(
        metrics.sort_values(["cohort", "segment", "method"]).to_string(
            index=False,
            formatters={
                "precision_at_3": "{:.2%}".format,
                "fill_rate": "{:.2%}".format,
            },
        )
    )
    print("\nCohort sizes:")
    print(sizes.sort_values(["cohort", "client_group"]).to_string(index=False))


if __name__ == "__main__":
    main()

