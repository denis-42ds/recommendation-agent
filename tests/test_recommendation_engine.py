import pytest

from recommendation_agent.engine import RecommendationEngine
from recommendation_agent.models import ProductOffer


def make_offer(
    item_id: str,
    group: str,
    offer_id: str,
    available: bool = True,
) -> ProductOffer:
    return ProductOffer(
        item_id=item_id,
        product_group=group,
        offer_id=offer_id,
        available=available,
        name=f"Product {group}",
    )


@pytest.fixture
def engine() -> RecommendationEngine:
    offers = {
        "GROUP-A": [make_offer("A1", "GROUP-A", "OFFER-A")],
        "GROUP-B": [make_offer("B1", "GROUP-B", "OFFER-B")],
        "GROUP-C": [make_offer("C1", "GROUP-C", "OFFER-C")],
        "GROUP-D": [make_offer("D1", "GROUP-D", "OFFER-D")],
    }

    return RecommendationEngine(
        adjacency={
            "A1": {"B1": 5, "C1": 2},
            "A2": {"B1": 3},
        },
        item_to_product_group={
            "A1": "GROUP-A",
            "A2": "GROUP-A",
            "B1": "GROUP-B",
            "C1": "GROUP-C",
            "D1": "GROUP-D",
        },
        offers_by_group=offers,
        popularity_by_segment={
            "B2B": {
                "GROUP-A": 100,
                "GROUP-B": 50,
                "GROUP-C": 30,
                "GROUP-D": 20,
            },
            "B2C": {
                "GROUP-A": 10,
                "GROUP-B": 5,
                "GROUP-C": 80,
                "GROUP-D": 40,
            },
        },
    )


def test_copurchase_ranks_candidates_and_excludes_history(
    engine: RecommendationEngine,
) -> None:
    result = engine.recommend(["A1"], "B2B", k=3)

    assert [item.product_id for item in result.recommendations] == [
        "OFFER-B",
        "OFFER-C",
        "OFFER-D",
    ]
    assert result.recommendations[0].reason_codes == ("co_purchase",)
    assert result.recommendations[0].score == 5
    assert result.personalized is True
    assert result.fill_rate == 1.0


def test_history_is_excluded_by_product_group_alias(
    engine: RecommendationEngine,
) -> None:
    result = engine.recommend(["A1", "A2"], "B2B", k=3)

    recommended_groups = {
        item.evidence["product_group"]
        for item in result.recommendations
    }
    assert "GROUP-A" not in recommended_groups


def test_multiple_history_items_aggregate_item_edges(
    engine: RecommendationEngine,
) -> None:
    result = engine.recommend(["A1", "A2"], "B2B", k=2)

    first = result.recommendations[0]
    assert first.product_id == "OFFER-B"
    assert first.score == 8
    assert len(first.evidence["edges"]) == 2
    assert "not a deduplicated product_group basket count" in (
        first.evidence["score_definition"]
    )


def test_cold_start_uses_segment_popularity(
    engine: RecommendationEngine,
) -> None:
    result = engine.recommend([], "B2C", k=3)

    assert [item.product_id for item in result.recommendations] == [
        "OFFER-C",
        "OFFER-D",
        "OFFER-A",
    ]
    assert result.personalized is False
    assert result.recommendations[0].reason_codes == (
        "cold_start_popularity",
    )



def test_popularity_fallback_fills_remaining_slots(
    engine: RecommendationEngine,
) -> None:
    result = engine.recommend(["A1"], "B2C", k=3)

    assert [item.product_id for item in result.recommendations] == [
        "OFFER-B",
        "OFFER-C",
        "OFFER-D",
    ]

    assert result.recommendations[0].reason_codes == ("co_purchase",)
    assert result.recommendations[1].reason_codes == ("co_purchase",)
    assert result.recommendations[2].reason_codes == ("popularity_fallback",)


def test_unavailable_offers_are_not_recommended() -> None:
    engine = RecommendationEngine(
        adjacency={},
        item_to_product_group={"A1": "A", "B1": "B"},
        offers_by_group={
            "A": [make_offer("A1", "A", "OA")],
            "B": [make_offer("B1", "B", "OB", available=False)],
        },
        popularity_by_segment={"B2B": {"A": 10, "B": 100}},
    )

    result = engine.recommend([], "B2B", k=3)

    assert [item.product_id for item in result.recommendations] == ["OA"]


def test_one_offer_per_product_group() -> None:
    engine = RecommendationEngine(
        adjacency={},
        item_to_product_group={
            "A1": "GROUP-A",
            "A2": "GROUP-A",
        },
        offers_by_group={
            "GROUP-A": [
                make_offer("A2", "GROUP-A", "OFFER-2"),
                make_offer("A1", "GROUP-A", "OFFER-1"),
            ],
        },
        popularity_by_segment={"B2B": {"GROUP-A": 10}},
    )

    result = engine.recommend([], "B2B", k=3)

    assert len(result.recommendations) == 1
    assert result.recommendations[0].product_id == "OFFER-1"


def test_b2b_and_b2c_popularity_are_separate(
    engine: RecommendationEngine,
) -> None:
    b2b = engine.recommend([], "B2B", k=2)
    b2c = engine.recommend([], "B2C", k=2)

    assert b2b.recommendations[0].product_id == "OFFER-A"
    assert b2c.recommendations[0].product_id == "OFFER-C"


def test_fill_rate_is_less_than_one_when_catalog_is_small() -> None:
    engine = RecommendationEngine(
        adjacency={},
        item_to_product_group={"A1": "A"},
        offers_by_group={"A": [make_offer("A1", "A", "OA")]},
        popularity_by_segment={"B2B": {"A": 10}},
    )

    result = engine.recommend([], "B2B", k=3)

    assert len(result.recommendations) == 1
    assert result.fill_rate == pytest.approx(1 / 3)


def test_invalid_client_group_raises_error(
    engine: RecommendationEngine,
) -> None:
    with pytest.raises(ValueError, match="Unsupported client_group"):
        engine.recommend([], "UNKNOWN")


def test_invalid_k_raises_error(
    engine: RecommendationEngine,
) -> None:
    with pytest.raises(ValueError, match="k must be >= 1"):
        engine.recommend([], "B2B", k=0)
