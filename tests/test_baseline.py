import pandas as pd

from scripts.run_baseline import (
    build_item_cooccurrence,
    build_popularity_ranking,
    recommend_co_purchase,
    recommend_popularity,
    split_train_test,
)


def test_september_first_belongs_to_test() -> None:
    sales = pd.DataFrame(
        [
            {
                "order_id": "O1",
                "client_id": "C1",
                "order_week": pd.Timestamp("2026-08-31"),
                "item_id": "A",
            },
            {
                "order_id": "O2",
                "client_id": "C1",
                "order_week": pd.Timestamp("2026-09-01"),
                "item_id": "B",
            },
        ]
    )

    train, test = split_train_test(sales)

    assert set(train["item_id"]) == {"A"}
    assert set(test["item_id"]) == {"B"}


def test_popularity_counts_unique_clients_not_orders() -> None:
    train = pd.DataFrame(
        [
            {"client_id": "C1", "item_id": "A"},
            {"client_id": "C1", "item_id": "A"},
            {"client_id": "C1", "item_id": "B"},
            {"client_id": "C2", "item_id": "B"},
            {"client_id": "C3", "item_id": "A"},
        ]
    )

    ranking, counts = build_popularity_ranking(train)

    assert counts == {"A": 2, "B": 2}
    assert ranking == ["A", "B"]


def test_copurchase_uses_composite_basket_key() -> None:
    train = pd.DataFrame(
        [
            {
                "order_id": "O1",
                "order_week": pd.Timestamp("2026-08-03"),
                "item_id": "A",
            },
            {
                "order_id": "O1",
                "order_week": pd.Timestamp("2026-08-03"),
                "item_id": "B",
            },
            {
                "order_id": "O1",
                "order_week": pd.Timestamp("2026-08-10"),
                "item_id": "A",
            },
            {
                "order_id": "O1",
                "order_week": pd.Timestamp("2026-08-10"),
                "item_id": "B",
            },
        ]
    )

    graph = build_item_cooccurrence(train)

    assert graph["A"]["B"] == 2
    assert graph["B"]["A"] == 2


def test_popularity_recommendations_use_item_id_tiebreak() -> None:
    counts = {"B": 5, "A": 5, "C": 3}

    recommendations = recommend_popularity(
        history=set(),
        popularity_counts=counts,
        k=3,
    )

    assert recommendations == ["A", "B", "C"]


def test_copurchase_tiebreak_uses_popularity_then_item_id() -> None:
    graph = {
        "H": {
            "B": 2,
            "A": 2,
            "C": 2,
        }
    }
    popularity = {
        "A": 5,
        "B": 7,
        "C": 7,
    }

    recommendations = recommend_co_purchase(
        history={"H"},
        graph=graph,
        popularity_counts=popularity,
        k=3,
    )

    assert recommendations == ["B", "C", "A"]


def test_recommendations_exclude_seen_items() -> None:
    counts = {"A": 10, "B": 8, "C": 5}

    recommendations = recommend_popularity(
        history={"A"},
        popularity_counts=counts,
        k=3,
    )

    assert recommendations == ["B", "C"]
