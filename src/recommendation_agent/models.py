from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductOffer:
    item_id: str
    product_group: str
    offer_id: str
    available: bool
    name: str
    url: str = ""
    vendor: str = ""
    category_path: tuple[str, ...] = ()
    description: str = ""

    @property
    def product_id(self) -> str:
        """Public recommendation identifier: catalog offer_id."""
        return self.offer_id


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    recommendation_type: str
    score: float
    reason_codes: tuple[str, ...]
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reason_codes"] = list(self.reason_codes)
        return result


@dataclass(frozen=True)
class RecommendationResult:
    client_group: str
    recommendations: tuple[Recommendation, ...]
    personalized: bool
    fill_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_group": self.client_group,
            "personalized": self.personalized,
            "fill_rate": self.fill_rate,
            "recommendations": [
                recommendation.to_dict()
                for recommendation in self.recommendations
            ],
        }
