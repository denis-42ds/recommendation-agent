import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from recommendation_agent.engine import RecommendationEngine
from recommendation_agent.models import ProductOffer
from scripts.run_baseline import (
    build_client_histories,
    build_product_group_mapping,
    load_data,
    split_train_test,
)


@dataclass
class RecommendationData:
    engine: RecommendationEngine
    histories: dict[str, set[str]]
    client_groups: dict[str, str]

    def recommend_for_client(self, client_id: str, k: int = 3):
        normalized_id = str(client_id).strip()
        if normalized_id not in self.client_groups:
            raise KeyError(f"Unknown client_id: {client_id}")

        return self.engine.recommend(
            history_item_ids=self.histories.get(normalized_id, set()),
            client_group=self.client_groups[normalized_id],
            k=k,
        )


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_adjacency(graph_path: Path) -> dict[str, dict[str, int]]:
    graph = _read_json(graph_path)
    adjacency: dict[str, dict[str, int]] = defaultdict(dict)

    for edge in graph.get("edges", []):
        item_a = str(edge["item_id_a"]).strip()
        item_b = str(edge["item_id_b"]).strip()
        basket_count = int(edge["basket_count"])

        if item_a == item_b or basket_count <= 0:
            continue

        adjacency[item_a][item_b] = basket_count
        adjacency[item_b][item_a] = basket_count

    return dict(adjacency)


def _load_offers(
    matched_products_path: Path,
    item_to_product_group: dict[str, str],
) -> dict[str, list[ProductOffer]]:
    records = _read_json(matched_products_path)
    offers_by_group: dict[str, list[ProductOffer]] = defaultdict(list)
    seen_offer_ids: set[str] = set()

    for record in records:
        item_id = str(record.get("item_id", "")).strip()
        offer_id = str(record.get("offer_id", "")).strip()

        if not item_id or not offer_id:
            continue

        product_group = item_to_product_group.get(item_id)
        if not product_group:
            continue

        # An offer_id must not produce duplicate recommendations.
        if offer_id in seen_offer_ids:
            continue
        seen_offer_ids.add(offer_id)

        category_path = record.get("category_path") or []
        if not isinstance(category_path, list):
            category_path = []

        offer = ProductOffer(
            item_id=item_id,
            product_group=product_group,
            offer_id=offer_id,
            available=record.get("available") is True,
            name=str(record.get("name") or offer_id),
            url=str(record.get("url") or ""),
            vendor=str(record.get("vendor") or ""),
            category_path=tuple(str(value) for value in category_path),
            description=str(record.get("description") or ""),
        )
        offers_by_group[product_group].append(offer)

    return dict(offers_by_group)


def _build_segment_popularity(
    train: pd.DataFrame,
    clients: pd.DataFrame,
    item_to_product_group: dict[str, str],
) -> dict[str, dict[str, int]]:
    sales = train[["client_id", "item_id"]].copy()
    sales["product_group"] = sales["item_id"].map(item_to_product_group)
    sales = sales.dropna(subset=["product_group"])

    # Use only client_id and client_group. No industry/profile fields.
    client_segments = clients[["client_id", "client_group"]].drop_duplicates(
        subset=["client_id"]
    )
    sales = sales.merge(
        client_segments,
        on="client_id",
        how="inner",
        validate="many_to_one",
    )

    sales = sales.drop_duplicates(
        subset=["client_id", "product_group", "client_group"]
    )

    counts = (
        sales.groupby(["client_group", "product_group"])["client_id"]
        .nunique()
        .to_dict()
    )

    result: dict[str, dict[str, int]] = {"B2B": {}, "B2C": {}}
    for (client_group, product_group), count in counts.items():
        normalized_group = str(client_group).strip().upper()
        if normalized_group in result:
            result[normalized_group][str(product_group)] = int(count)

    return result


def load_recommendation_data(
    workbook_path: str | Path,
    graph_path: str | Path = "artifacts/product_graph/graph.json",
    matched_products_path: str | Path = "artifacts/catalog/matched_products.json",
) -> RecommendationData:
    workbook_path = Path(workbook_path)
    graph_path = Path(graph_path)
    matched_products_path = Path(matched_products_path)

    sales, clients = load_data(workbook_path)
    train, _ = split_train_test(sales)

    histories = build_client_histories(train)
    item_to_product_group = build_product_group_mapping(sales)

    adjacency = _load_adjacency(graph_path)
    offers_by_group = _load_offers(
        matched_products_path,
        item_to_product_group,
    )
    popularity = _build_segment_popularity(
        train,
        clients,
        item_to_product_group,
    )

    client_groups = {
        str(row.client_id).strip(): str(row.client_group).strip().upper()
        for row in clients[["client_id", "client_group"]].itertuples(index=False)
    }

    engine = RecommendationEngine(
        adjacency=adjacency,
        item_to_product_group=item_to_product_group,
        offers_by_group=offers_by_group,
        popularity_by_segment=popularity,
    )

    normalized_histories = {
        str(client_id).strip(): {
            str(item_id).strip() for item_id in item_ids
        }
        for client_id, item_ids in histories.items()
    }

    return RecommendationData(
        engine=engine,
        histories=normalized_histories,
        client_groups=client_groups,
    )
