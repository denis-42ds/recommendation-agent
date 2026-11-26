import json

import pandas as pd
import pytest

from scripts.build_product_graph import (
    build_product_graph,
    export_product_graph,
    prepare_train_sales,
)


@pytest.fixture
def sales() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # O1 in week 1: A, B, duplicate A.
            {"order_id": "O1", "order_week": "2026-08-03", "item_id": "A"},
            {"order_id": "O1", "order_week": "2026-08-03", "item_id": "B"},
            {"order_id": "O1", "order_week": "2026-08-03", "item_id": "A"},
            # Same order_id in another week: a separate basket.
            {"order_id": "O1", "order_week": "2026-08-10", "item_id": "A"},
            {"order_id": "O1", "order_week": "2026-08-10", "item_id": "C"},
            # Another basket: A, B, C.
            {"order_id": "O2", "order_week": "2026-08-17", "item_id": "A"},
            {"order_id": "O2", "order_week": "2026-08-17", "item_id": "B"},
            {"order_id": "O2", "order_week": "2026-08-17", "item_id": "C"},
            # Isolated product D.
            {"order_id": "O3", "order_week": "2026-08-31", "item_id": "D"},
            # September 1 is Test, not Train.
            {"order_id": "O4", "order_week": "2026-09-01", "item_id": "TEST_ONLY"},
        ]
    )


def test_prepare_train_sales_excludes_test_period(sales: pd.DataFrame) -> None:
    train = prepare_train_sales(sales)

    assert "TEST_ONLY" not in set(train["item_id"])
    assert train["order_week"].max() <= pd.Timestamp("2026-08-31")


def test_same_order_id_in_different_weeks_means_two_baskets(
    sales: pd.DataFrame,
) -> None:
    train = prepare_train_sales(sales)
    nodes, edges = build_product_graph(train)

    node_counts = nodes.set_index("item_id")["basket_count"].to_dict()
    edge_counts = {
        (row.item_id_a, row.item_id_b): row.basket_count
        for row in edges.itertuples(index=False)
    }

    assert node_counts == {
        "A": 3,
        "B": 2,
        "C": 2,
        "D": 1,
    }

    assert edge_counts == {
        ("A", "B"): 2,
        ("A", "C"): 2,
        ("B", "C"): 1,
    }


def test_graph_keeps_isolated_nodes(sales: pd.DataFrame) -> None:
    train = prepare_train_sales(sales)
    nodes, edges = build_product_graph(train)

    assert "D" in set(nodes["item_id"])
    assert not (
        (edges["item_id_a"] == "D")
        | (edges["item_id_b"] == "D")
    ).any()


def test_graph_has_no_self_loops_or_duplicate_edges(
    sales: pd.DataFrame,
) -> None:
    train = prepare_train_sales(sales)
    _, edges = build_product_graph(train)

    assert not (edges["item_id_a"] == edges["item_id_b"]).any()
    assert not edges.duplicated(
        subset=["item_id_a", "item_id_b"]
    ).any()
    assert (edges["item_id_a"] < edges["item_id_b"]).all()


def test_export_creates_consistent_csv_and_json(
    sales: pd.DataFrame,
    tmp_path,
) -> None:
    train = prepare_train_sales(sales)
    nodes, edges = build_product_graph(train)

    export_product_graph(nodes, edges, tmp_path)

    nodes_csv = pd.read_csv(tmp_path / "nodes.csv")
    edges_csv = pd.read_csv(tmp_path / "edges.csv")

    with (tmp_path / "graph.json").open(encoding="utf-8") as file:
        graph = json.load(file)

    assert len(nodes_csv) == graph["metadata"]["node_count"]
    assert len(edges_csv) == graph["metadata"]["edge_count"]
    assert graph["metadata"]["train_period_end"] == "2026-08-31"
    assert graph["metadata"]["basket_key"] == ["order_id", "order_week"]
    assert graph["schema_version"] == 2

    assert "basket_count" in nodes_csv.columns
    assert "basket_count" in edges_csv.columns

    assert "TEST_ONLY" not in {
        node["item_id"] for node in graph["nodes"]
    }


def test_prepare_train_sales_rejects_missing_columns() -> None:
    sales = pd.DataFrame([{"order_id": "O1", "item_id": "A"}])

    with pytest.raises(ValueError, match="order_week"):
        prepare_train_sales(sales)


def test_prepare_train_sales_rejects_empty_train() -> None:
    sales = pd.DataFrame(
        [
            {
                "order_id": "O1",
                "order_week": "2026-09-01",
                "item_id": "A",
            }
        ]
    )

    with pytest.raises(ValueError, match="Train пустой"):
        prepare_train_sales(sales)
