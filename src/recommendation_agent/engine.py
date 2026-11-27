from collections import defaultdict
from typing import Iterable

from recommendation_agent.models import (
    ProductOffer,
    Recommendation,
    RecommendationResult,
)


class RecommendationEngine:
    """Deterministic Top-K cross-sell engine."""

    SUPPORTED_GROUPS = {"B2B", "B2C"}

    def __init__(
        self,
        adjacency: dict[str, dict[str, int]],
        item_to_product_group: dict[str, str],
        offers_by_group: dict[str, list[ProductOffer]],
        popularity_by_segment: dict[str, dict[str, int]],
    ) -> None:
        self.adjacency = adjacency
        self.item_to_product_group = item_to_product_group
        self.offers_by_group = offers_by_group
        self.popularity_by_segment = popularity_by_segment

        self._offer_by_group = {}
        for group, offers in offers_by_group.items():
            available = [offer for offer in offers if offer.available]
            if available:
                self._offer_by_group[group] = sorted(
                    available,
                    key=lambda offer: (offer.offer_id, offer.item_id),
                )[0]

    def _get_popularity(self, client_group: str) -> dict[str, int]:
        return self.popularity_by_segment.get(client_group, {})

    def _get_history_groups(
        self,
        history_item_ids: set[str],
    ) -> set[str]:
        return {
            self.item_to_product_group[item_id]
            for item_id in history_item_ids
            if item_id in self.item_to_product_group
        }

    def _build_copurchase_candidates(
        self,
        history_item_ids: set[str],
        seen_groups: set[str],
    ) -> tuple[dict[str, int], dict[str, list[dict[str, object]]]]:
        scores: dict[str, int] = defaultdict(int)
        evidence: dict[str, list[dict[str, object]]] = defaultdict(list)

        for source_item_id in sorted(history_item_ids):
            for candidate_item_id, basket_count in self.adjacency.get(
                source_item_id, {}
            ).items():
                candidate_group = self.item_to_product_group.get(
                    candidate_item_id
                )

                if not candidate_group or candidate_group in seen_groups:
                    continue
                if candidate_group not in self._offer_by_group:
                    continue

                scores[candidate_group] += int(basket_count)
                evidence[candidate_group].append(
                    {
                        "source_item_id": source_item_id,
                        "candidate_item_id": candidate_item_id,
                        "basket_count": int(basket_count),
                    }
                )

        return dict(scores), dict(evidence)

    def _popularity_candidates(
        self,
        client_group: str,
        excluded_groups: set[str],
    ) -> list[str]:
        popularity = self._get_popularity(client_group)

        candidates = [
            group
            for group in popularity
            if group not in excluded_groups
            and group in self._offer_by_group
        ]

        return sorted(
            candidates,
            key=lambda group: (-popularity[group], group),
        )

    @staticmethod
    def _copurchase_explanation(
        offer: ProductOffer,
        evidence: list[dict[str, object]],
    ) -> str:
        source_items = sorted(
            {str(item["source_item_id"]) for item in evidence}
        )
        return (
            f"Товар {offer.name} часто встречался в одной корзине "
            f"с товарами из истории покупок клиента "
            f"(исходные товары: {', '.join(source_items)})."
        )

    @staticmethod
    def _popularity_explanation(
        offer: ProductOffer,
        client_group: str,
    ) -> str:
        return (
            f"Товар {offer.name} входит в число популярных товаров "
            f"сегмента {client_group}. "
            "Рекомендация основана на агрегированной статистике покупок."
        )

    def recommend(
        self,
        history_item_ids: Iterable[str],
        client_group: str,
        k: int = 3,
    ) -> RecommendationResult:
        if k < 1:
            raise ValueError("k must be >= 1")

        normalized_group = str(client_group).strip().upper()
        if normalized_group not in self.SUPPORTED_GROUPS:
            raise ValueError(
                f"Unsupported client_group: {client_group!r}. "
                f"Expected one of {sorted(self.SUPPORTED_GROUPS)}"
            )

        history = {
            str(item_id).strip()
            for item_id in history_item_ids
            if str(item_id).strip()
        }
        seen_groups = self._get_history_groups(history)
        popularity = self._get_popularity(normalized_group)

        recommendations: list[Recommendation] = []
        selected_groups: set[str] = set()

        # Cold-start: no purchase history, popularity only.
        if not history:
            for group in self._popularity_candidates(
                normalized_group,
                excluded_groups=set(),
            ):
                offer = self._offer_by_group[group]
                recommendations.append(
                    Recommendation(
                        product_id=offer.product_id,
                        recommendation_type="cross_sell",
                        score=float(popularity[group]),
                        reason_codes=("cold_start_popularity",),
                        evidence={
                            "product_group": group,
                            "segment": normalized_group,
                            "distinct_clients": popularity[group],
                            "personalized": False,
                        },
                        explanation=self._popularity_explanation(
                            offer,
                            normalized_group,
                        ),
                    )
                )
                selected_groups.add(group)
                if len(recommendations) >= k:
                    break

            return RecommendationResult(
                client_group=normalized_group,
                recommendations=tuple(recommendations),
                personalized=False,
                fill_rate=len(recommendations) / k,
            )

        # Personalized co-purchase candidates.
        copurchase_scores, copurchase_evidence = (
            self._build_copurchase_candidates(history, seen_groups)
        )

        ranked_groups = sorted(
            copurchase_scores,
            key=lambda group: (
                -copurchase_scores[group],
                -popularity.get(group, 0),
                group,
            ),
        )

        for group in ranked_groups:
            offer = self._offer_by_group[group]
            evidence = sorted(
                copurchase_evidence[group],
                key=lambda item: (
                    str(item["source_item_id"]),
                    str(item["candidate_item_id"]),
                ),
            )
            recommendations.append(
                Recommendation(
                    product_id=offer.product_id,
                    recommendation_type="cross_sell",
                    score=float(copurchase_scores[group]),
                    reason_codes=("co_purchase",),
                    evidence={
                        "product_group": group,
                        "co_purchase_score": copurchase_scores[group],
                        "edges": evidence,
                        "score_definition": (
                            "Sum of item-level co-purchase edge basket counts "
                            "across the client's history items. This is not "
                            "a deduplicated product_group basket count."
                        ),
                    },
                    explanation=self._copurchase_explanation(
                        offer,
                        evidence,
                    ),
                )
            )
            selected_groups.add(group)
            if len(recommendations) >= k:
                break

        # Fill remaining slots with segment popularity.
        if len(recommendations) < k:
            for group in self._popularity_candidates(
                normalized_group,
                excluded_groups=seen_groups | selected_groups,
            ):
                offer = self._offer_by_group[group]
                recommendations.append(
                    Recommendation(
                        product_id=offer.product_id,
                        recommendation_type="cross_sell",
                        score=float(popularity[group]),
                        reason_codes=("popularity_fallback",),
                        evidence={
                            "product_group": group,
                            "segment": normalized_group,
                            "distinct_clients": popularity[group],
                            "personalized": False,
                        },
                        explanation=self._popularity_explanation(
                            offer,
                            normalized_group,
                        ),
                    )
                )
                selected_groups.add(group)
                if len(recommendations) >= k:
                    break

        return RecommendationResult(
            client_group=normalized_group,
            recommendations=tuple(recommendations),
            personalized=True,
            fill_rate=len(recommendations) / k,
        )
