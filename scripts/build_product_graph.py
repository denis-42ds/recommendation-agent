
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import pandas as pd

TRAIN_END = pd.Timestamp("2026-08-31")

REQUIRED_SALES_COLUMNS = {
    "order_id",
    "order_week",
    "item_id",
}

NODE_COLUMNS = ["item_id", "order_count"]
EDGE_COLUMNS = ["item_id_a", "item_id_b", "order_count"]


def normalize_id(series: pd.Series) -> pd.Series:
    """Normalize identifiers without converting them to numeric values."""
    normalized = series.astype("string").str.strip()
    return normalized.replace("", pd.NA)


def prepare_train_sales(sales: pd.DataFrame) -> pd.DataFrame:
    """Validate sales data and retain only rows from the training period."""
    missing = REQUIRED_SALES_COLUMNS - set(sales.columns)
    if missing:
        raise ValueError(
            f"В листе 'Продажи' отсутствуют колонки: {sorted(missing)}"
        )

    train = sales.copy()

    for column in ("order_id", "item_id"):
        train[column] = normalize_id(train[column])

    train["order_week"] = pd.to_datetime(
        train["order_week"],
        errors="coerce",
    )

    train = train.dropna(
        subset=["order_id", "item_id", "order_week"]
    ).copy()

    train = train[train["order_week"] <= TRAIN_END].copy()

    if train.empty:
        raise ValueError(
            "Train пустой после фильтрации. "
            "Проверьте данные и значения order_week."
        )

    return train


def load_train_sales(path: Path) -> pd.DataFrame:
    """Load sales from the organizer workbook and apply the train cutoff."""
    if not path.exists():
        raise FileNotFoundError(f"Файл датасета не найден: {path}")

    sales = pd.read_excel(
        path,
        sheet_name="Продажи",
        engine="openpyxl",
    )

    return prepare_train_sales(sales)


def build_product_graph(
    train: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build graph nodes and undirected weighted edges from training orders.

    Each product is counted once per order.
    Each unordered product pair contributes one edge count per order.
    Products appearing in only one-product orders remain isolated nodes.
    """
    missing = REQUIRED_SALES_COLUMNS - set(train.columns)
    if missing:
        raise ValueError(
            f"В данных отсутствуют колонки: {sorted(missing)}"
        )

    # Deduplicate product occurrences within each order.
    order_items = train[["order_id", "item_id"]].drop_duplicates()

    node_counts = (
        order_items.groupby("item_id")["order_id"]
        .nunique()
        .rename("order_count")
        .reset_index()
        .sort_values("item_id", kind="stable")
        .reset_index(drop=True)
    )

    edge_counts: dict[tuple[str, str], int] = {}

    grouped_orders = (
        order_items.groupby("order_id")["item_id"]
        .apply(lambda values: sorted(set(values)))
    )

    for items in grouped_orders:
        for item_a, item_b in combinations(items, 2):
            pair = (item_a, item_b)
            edge_counts[pair] = edge_counts.get(pair, 0) + 1

    edge_rows = [
        {
            "item_id_a": item_a,
            "item_id_b": item_b,
            "order_count": count,
        }
        for (item_a, item_b), count in sorted(edge_counts.items())
    ]

    nodes = node_counts[NODE_COLUMNS].copy()
    edges = pd.DataFrame(edge_rows, columns=EDGE_COLUMNS)

    return nodes, edges


def export_product_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Export graph nodes and edges as CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = nodes[NODE_COLUMNS].copy()
    edges = edges[EDGE_COLUMNS].copy()

    nodes.to_csv(
        output_dir / "nodes.csv",
        index=False,
        encoding="utf-8",
    )
    edges.to_csv(
        output_dir / "edges.csv",
        index=False,
        encoding="utf-8",
    )

    graph = {
        "schema_version": 1,
        "metadata": {
            "train_period_end": TRAIN_END.date().isoformat(),
            "directed": False,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_definition": (
                "One node per distinct item_id present in training sales."
            ),
            "edge_definition": (
                "An undirected edge exists when two distinct products "
                "appear in the same order. Weight is the number of "
                "unique orders containing the pair."
            ),
        },
        "nodes": [
            {
                "item_id": str(row.item_id),
                "order_count": int(row.order_count),
            }
            for row in nodes.itertuples(index=False)
        ],
        "edges": [
            {
                "item_id_a": str(row.item_id_a),
                "item_id_b": str(row.item_id_b),
                "order_count": int(row.order_count),
            }
            for row in edges.itertuples(index=False)
        ],
    }

    with (output_dir / "graph.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            graph,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a weighted product co-purchase graph from train sales."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "docs/source-materials/Датасет_Рекомендации_ЛК_v3.xlsx"
        ),
        help="Path to the organizer Excel workbook.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/product_graph"),
        help="Directory for graph CSV and JSON files.",
    )

    args = parser.parse_args()

    train = load_train_sales(args.input)
    nodes, edges = build_product_graph(train)
    export_product_graph(nodes, edges, args.output)

    print("\nProduct graph build completed.")
    print(f"Input:       {args.input}")
    print(f"Train rows:  {len(train)}")
    print(f"Train end:   {TRAIN_END.date()}")
    print(f"Nodes:       {len(nodes)}")
    print(f"Edges:       {len(edges)}")
    print(f"Output:      {args.output}")


if __name__ == "__main__":
    main()

