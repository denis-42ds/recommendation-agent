# Architecture — Recommendation Agent MVP

**Дата актуализации:** 27.11.2026
**Статус:** DECISION — локальная архитектура MVP реализована и проверена пользователем.

## 1. Архитектурный принцип

Модульный монолит: один Python-процесс, Streamlit UI, Recommendation Engine и загрузчик подготовленных данных. Локальная демонстрация не требует внешних сервисов или LLM.

## 2. Поток обработки

```text
Streamlit UI
   |
   v
Customer Context
   |
   v
Candidate Generation
   |-- Co-purchase candidates from item graph
   `-- Popularity fallback by segment
   |
   v
Business Filtering
   |-- exclude purchased product_group
   |-- catalog membership / available offers
   `-- one offer per product_group
   |
   v
Ranking / Scoring
   |
   v
Evidence-based Explanation
   |
   v
Top-3 RecommendationResult
```

## 3. Компоненты

### UI — `app.py`
- выбор сегмента B2B/B2C;
- выбор клиента с историей или cold-start;
- отображение сегмента и истории;
- вызов движка;
- отображение рекомендаций, score, причин, evidence и объяснения;
- переход к карточке предложения по URL, если он присутствует в каталоге.

Локальный запуск `streamlit run app.py` подтверждён пользователем. Публичный деплой не подтверждён.

### Recommendation Engine — `src/recommendation_agent/engine.py`
- принимает историю `item_id`, сегмент и `k`;
- получает co-purchase кандидатов из item-графа;
- агрегирует кандидатов по товарной идентичности для выдачи;
- исключает уже купленные группы;
- использует co-purchase прежде popularity fallback;
- выдаёт детерминированный `RecommendationResult`.

### Models — `src/recommendation_agent/models.py`
`ProductOffer` содержит `item_id`, `product_group`, `offer_id`, `available`, `name`, `url`, `vendor`, `category_path`, `description`. Поля цены нет.

`Recommendation` содержит `product_id`, `recommendation_type`, `score`, `reason_codes`, `evidence`, `explanation`.

`RecommendationResult` содержит `client_group`, `recommendations`, `personalized`, `fill_rate`.

### Data access — `src/recommendation_agent/data_loader.py`
- загружает workbook, graph JSON и `matched_products.json`;
- строит adjacency и сегментную popularity;
- формирует histories и client groups;
- передаёт готовые структуры движку.

Существующий baseline не переписывается ради UI.

## 4. Идентичность товаров и уровни данных

Это важное разграничение:

| Контур | Идентификатор | Правило |
|---|---|---|
| Sales / baseline | `item_id` | Сохранять исходную детализацию |
| Product graph | `item_id` | Узлы и рёбра остаются на уровне item |
| Engine filtering/dedup | `product_group` | Исключить уже купленную группу и дубли в выдаче |
| Catalog offer | `offer_id` | Конкретное предложение каталога |
| Recommendation output | `product_id = offer_id` | Идентификатор разрешается в каталоге |

Внутри одной `product_group` выбирается одно доступное предложение детерминированно по `(offer_id, item_id)`. Это не означает, что разные `item_id` объединяются в baseline или графе.

## 5. Источники и ограничения данных

- Sales workbook — история покупок.
- `artifacts/product_graph/graph.json` — Train-граф: 813 узлов и 1 986 рёбер.
- `artifacts/catalog/matched_products.json` — 552 сопоставленные записи предложений.
- 438 из 817 sales `item_id` имеют сопоставление в последнем подтверждённом запуске каталога.
- Только доступные предложения используются движком.
- Исторического snapshot каталога/наличия нет.

Не выводить техническую совместимость из совместной покупки. Не выводить цену: поле цены отсутствует в `ProductOffer`.

## 6. Алгоритм

### Candidate Generation
1. Уникальная история клиента на уровне `item_id`.
2. Соседи из неориентированного co-purchase графа.
3. Суммирование `basket_count` по товарам истории.
4. Popularity fallback по сегменту для незаполненных позиций.

### Business Filtering
- фильтр ранее приобретённых `product_group`;
- фильтр по доступному сопоставленному каталогу;
- одна позиция на `product_group`;
- B2B/B2C сегментная популярность;
- для B2C не используются `industry` и корпоративный профиль.

### Ranking / Explanation
Ранжирование детерминированное: co-purchase приоритетнее fallback; evidence и reason codes формируются из реальных счётчиков и источников. LLM не входит в критический путь.

## 7. Результаты локальной диагностики

Пользователь подтвердил диагностический прогон по 19 008 клиентам:
- Fill Rate 100% для ALL/B2B/B2C;
- Top-3 заполнен всем клиентам;
- 17 457 клиентов с историей и 1 551 без истории;
- 40 468 co-purchase позиций;
- 11 903 popularity fallback позиции;
- 4 653 cold-start popularity позиции.

Эти значения описывают заполненность и состав выдачи, но не являются оценкой Precision или бизнес-эффекта.

## 8. Тестирование

Подтверждённый локальный результат:
```text
ruff check: All checks passed
git diff --check: без ошибок
pytest: 45 passed
```

Дополнительно пользователь запускал:
```bash
python -m scripts.check_recommendation_engine
python -m scripts.evaluate_recommendation_engine
streamlit run app.py
```

## 9. Развёртывание

- Локальный Streamlit — подтверждённый путь.
- Docker — OPEN до подтверждения build/run.
- Cloud Run — OPEN до подтверждения deploy и публичного smoke test.
- Целевой регион Cloud Run: `asia-southeast3` (Bangkok).
- Предварительные параметры ресурсов не считать подтверждёнными настройками до деплоя.

## 10. Архитектурные ограничения

Не добавлять FastAPI, внешнюю БД, RAG, vector DB, микросервисы или multi-agent без конкретной блокирующей причины.
