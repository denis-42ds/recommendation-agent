from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from recommendation_agent.data_loader import load_recommendation_data

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

WORKBOOK_PATH = (
    PROJECT_ROOT
    / "docs"
    / "source-materials"
    / "Датасет_Рекомендации_ЛК_v5.xlsx"
)

GRAPH_PATH = PROJECT_ROOT / "artifacts" / "product_graph" / "graph.json"

MATCHED_PRODUCTS_PATH = (
    PROJECT_ROOT / "artifacts" / "catalog" / "matched_products.json"
)

TOP_K = 3

REASON_LABELS = {
    "co_purchase": "Совместные покупки",
    "popularity_fallback": "Популярность сегмента (fallback)",
    "cold_start_popularity": "Популярность сегмента (cold-start)",
}


# ---------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------

@st.cache_resource(show_spinner="Загружаю данные и Recommendation Engine...")
def get_recommendation_data(
    workbook_path: str,
    graph_path: str,
    matched_products_path: str,
):
    return load_recommendation_data(
        workbook_path=workbook_path,
        graph_path=graph_path,
        matched_products_path=matched_products_path,
    )


@st.cache_data(show_spinner=False)
def load_catalog_records(path: str) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("matched_products.json должен содержать JSON-массив")

    return records


def build_catalog_indexes(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    offers_by_id: dict[str, dict[str, Any]] = {}
    names_by_item_id: dict[str, str] = {}

    for record in records:
        offer_id = str(record.get("offer_id") or "").strip()
        item_id = str(record.get("item_id") or "").strip()
        name = str(record.get("name") or "").strip()

        if offer_id:
            offers_by_id[offer_id] = record

        if item_id and name:
            names_by_item_id[item_id] = name

    return offers_by_id, names_by_item_id


# ---------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------

def render_product_history(
    history_item_ids: set[str],
    names_by_item_id: dict[str, str],
) -> None:
    if not history_item_ids:
        st.info("История покупок отсутствует. Это сценарий cold-start.")
        return

    with st.expander(
        f"История покупок — {len(history_item_ids)} уникальных товаров",
        expanded=True,
    ):
        for item_id in sorted(history_item_ids):
            name = names_by_item_id.get(item_id)

            if name:
                st.markdown(f"- **{name}**")
                st.caption(f"`{item_id}`")
            else:
                st.markdown(f"- `{item_id}` — название отсутствует в каталоге")


def render_recommendation(
    index: int,
    recommendation: Any,
    offers_by_id: dict[str, dict[str, Any]],
) -> None:
    product = offers_by_id.get(recommendation.product_id, {})

    name = str(product.get("name") or recommendation.product_id)
    vendor = str(product.get("vendor") or "")
    url = str(product.get("url") or "")
    category_path = product.get("category_path") or []

    reason_codes = recommendation.reason_codes
    reason_labels = [
        REASON_LABELS.get(reason, reason)
        for reason in reason_codes
    ]

    with st.container(border=True):
        header_left, header_right = st.columns([4, 1])

        with header_left:
            st.subheader(f"{index}. {name}")

        with header_right:
            st.metric("Score", f"{recommendation.score:g}")

        st.caption(
            f"Product ID: `{recommendation.product_id}`"
            f" · Тип: `{recommendation.recommendation_type}`"
        )

        if vendor:
            st.write(f"**Производитель / поставщик:** {vendor}")

        if category_path:
            st.write(
                "**Категория:** "
                + " → ".join(str(value) for value in category_path)
            )

        if reason_labels:
            st.write("**Причина:** " + ", ".join(reason_labels))

        st.write(recommendation.explanation)

        if url.startswith(("https://", "http://")):
            st.link_button("Открыть товар в каталоге", url)

        with st.expander("Технические детали и Evidence"):
            st.write("**Reason codes**")
            st.json(list(reason_codes))

            st.write("**Evidence**")
            st.json(recommendation.evidence)


# ---------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Recommendation Agent",
    page_icon="🛍️",
    layout="wide",
)

st.title("Recommendation Agent")
st.caption(
    "Softline · Демонстрация Cross-sell рекомендаций · B2B / B2C"
)

# Validate required artifacts before loading.
required_paths = {
    "Workbook": WORKBOOK_PATH,
    "Product graph": GRAPH_PATH,
    "Matched catalog": MATCHED_PRODUCTS_PATH,
}

missing_paths = [
    f"{name}: `{path}`"
    for name, path in required_paths.items()
    if not path.exists()
]

if missing_paths:
    st.error("Не найдены необходимые файлы:")
    for path in missing_paths:
        st.markdown(f"- {path}")
    st.stop()

try:
    data = get_recommendation_data(
        str(WORKBOOK_PATH),
        str(GRAPH_PATH),
        str(MATCHED_PRODUCTS_PATH),
    )
    catalog_records = load_catalog_records(str(MATCHED_PRODUCTS_PATH))
    offers_by_id, names_by_item_id = build_catalog_indexes(catalog_records)

except Exception as exc:
    st.error(f"Не удалось загрузить данные: {exc}")
    st.exception(exc)
    st.stop()


# ---------------------------------------------------------------------
# Sidebar: customer selection
# ---------------------------------------------------------------------

st.sidebar.header("Выбор клиента")

segment = st.sidebar.radio(
    "Сегмент",
    options=["B2B", "B2C"],
    horizontal=True,
)

customer_mode = st.sidebar.radio(
    "Тип клиента",
    options=["С историей покупок", "Cold-start"],
)

if customer_mode == "С историей покупок":
    candidate_ids = [
        client_id
        for client_id, group in data.client_groups.items()
        if group == segment and data.histories.get(client_id)
    ]
else:
    candidate_ids = [
        client_id
        for client_id, group in data.client_groups.items()
        if group == segment and not data.histories.get(client_id)
    ]

candidate_ids.sort()

st.sidebar.caption(f"Доступно клиентов: {len(candidate_ids):,}".replace(",", " "))

if not candidate_ids:
    st.warning("Для выбранного сегмента и типа клиента нет записей.")
    st.stop()

client_id = st.sidebar.selectbox(
    "Демонстрационный клиент",
    options=candidate_ids,
    index=0,
)

generate = st.sidebar.button(
    "Сформировать рекомендации",
    type="primary",
    use_container_width=True,
)

# The selected customer is evaluated on every rerun.
# The button provides an explicit demo action but is not required
# to keep the result visible after changing the selection.
history = data.histories.get(client_id, set())
client_group = data.client_groups[client_id]

result = data.engine.recommend(
    history_item_ids=history,
    client_group=client_group,
    k=TOP_K,
)


# ---------------------------------------------------------------------
# Customer context
# ---------------------------------------------------------------------

st.divider()
st.header("Профиль клиента")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Client ID", client_id)
col2.metric("Сегмент", client_group)
col3.metric("Товаров в истории", len(history))
col4.metric(
    "Тип рекомендаций",
    "Персональные" if result.personalized else "Cold-start",
)

if result.personalized:
    st.success("Рекомендации учитывают историю покупок клиента.")
else:
    st.info(
        "Cold-start: история покупок отсутствует. "
        "Используется популярность товаров в соответствующем сегменте."
    )

st.subheader("История покупок")
render_product_history(history, names_by_item_id)


# ---------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------

st.divider()
st.header("Рекомендации Cross-sell")

metric_col1, metric_col2, metric_col3 = st.columns(3)

metric_col1.metric(
    "Рекомендаций",
    f"{len(result.recommendations)} / {TOP_K}",
)

metric_col2.metric(
    "Fill Rate",
    f"{result.fill_rate:.0%}",
)

metric_col3.metric(
    "Персонализация",
    "Да" if result.personalized else "Нет",
)

if not result.recommendations:
    st.warning("Для клиента не найдено доступных рекомендаций.")
else:
    for index, recommendation in enumerate(
        result.recommendations,
        start=1,
    ):
        render_recommendation(
            index=index,
            recommendation=recommendation,
            offers_by_id=offers_by_id,
        )

if len(result.recommendations) < TOP_K:
    st.warning(
        "Недостаточно доступных кандидатов для полного Top-3. "
        "Отображены только найденные рекомендации."
    )

st.divider()

with st.expander("О системе"):
    st.markdown(
        """
        **Recommendation Engine MVP**

        - Candidate Generation: co-purchase.
        - Fallback: популярность товаров в сегменте.
        - Сегменты B2B и B2C обрабатываются раздельно.
        - Для B2C не используются отрасль и корпоративный профиль.
        - Ранее приобретённые товары исключаются.
        - Рекомендации строятся только по сопоставленным предложениям каталога.
        - Объяснения формируются детерминированно на основе Evidence.
        - LLM не участвует в критическом пути.
        """
    )
