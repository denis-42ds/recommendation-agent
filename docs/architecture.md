# Architecture — Recommendation Agent MVP

**Дата актуализации:** 27.11.2026
**Статус:** CONFIRMED — локальная архитектура, Docker-сборка и Cloud Run deployment реализованы.

## 1. Архитектурный принцип

Модульный монолит: один Python-процесс, Streamlit UI, Recommendation Engine и загрузчик подготовленных данных.

Архитектура выбрана с учётом ограничений MVP:

- один разработчик;
- ограниченные сроки;
- минимум инфраструктурных зависимостей;
- воспроизводимый детерминированный алгоритм;
- отсутствие обязательной зависимости от LLM.

Для работы приложения не требуются отдельные микросервисы, FastAPI, внешняя БД, vector DB или RAG.

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

Локальный запуск `streamlit run app.py` подтверждён пользователем. Работа UI в Docker и доступность публичного Cloud Run URL также подтверждены.

### Recommendation Engine — `src/recommendation_agent/engine.py`

- принимает историю `item_id`, сегмент и `k`;
- получает co-purchase кандидатов из item-графа;
- агрегирует кандидатов по товарной идентичности для выдачи;
- исключает уже купленные группы;
- использует co-purchase прежде popularity fallback;
- выдаёт детерминированный `RecommendationResult`.

### Models — `src/recommendation_agent/models.py`

`ProductOffer` содержит:

- `item_id`;
- `product_group`;
- `offer_id`;
- `available`;
- `name`;
- `url`;
- `vendor`;
- `category_path`;
- `description`.

Поля цены нет.

`Recommendation` содержит:

- `product_id`;
- `recommendation_type`;
- `score`;
- `reason_codes`;
- `evidence`;
- `explanation`.

`RecommendationResult` содержит:

- `client_group`;
- `recommendations`;
- `personalized`;
- `fill_rate`.

### Data access — `src/recommendation_agent/data_loader.py`

- загружает workbook, graph JSON и `matched_products.json`;
- строит adjacency и сегментную popularity;
- формирует histories и client groups;
- передаёт готовые структуры движку.

Существующий baseline не переписывается ради UI.

## 4. Идентичность товаров и уровни данных

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

Ранжирование детерминированное: co-purchase приоритетнее fallback; evidence и reason codes формируются из реальных счётчиков и источников.

LLM не входит в критический путь и не вызывается при генерации рекомендаций.

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

Docker build/run также подтверждены пользователем.

## 9. Docker

Используется Dockerfile на базе:

```dockerfile
FROM python:3.11-slim
```

Контейнер запускает Streamlit на порту `8080` или на порту, переданном через переменную окружения `PORT`.

Основная команда запуска:

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080}
```

В контейнер включаются:

- приложение;
- исходный код `src/`;
- `scripts/run_baseline.py`;
- граф `artifacts/product_graph/graph.json`;
- каталог `artifacts/catalog/matched_products.json`;
- Excel-файл датасета.

Для временных конфигурационных и кэш-файлов Streamlit/Matplotlib используются каталоги под `/tmp/app-home`. Контейнер запускается от непривилегированного пользователя `app`.

Локальная сборка и запуск контейнера подтверждены пользователем. UI открывался на `http://localhost:8080`.

## 10. Google Cloud Run

### Подтверждённая конфигурация

| Параметр | Значение |
|---|---|
| Google Cloud project | `recommendation-agent-demo` |
| Cloud Run service | `recommendation-agent` |
| Region | `asia-southeast3` |
| Region name | Bangkok |
| Public URL | https://recommendation-agent-ug7evithwa-eu.a.run.app |
| Последняя подтверждённая revision | `recommendation-agent-00002-j5w` |
| Traffic | 100% на revision `recommendation-agent-00002-j5w` |
| Concurrency | 80 |
| Artifact Registry repository | `recommendation-agent` |
| Artifact Registry location | `asia-southeast3` |

Образ:

```text
asia-southeast3-docker.pkg.dev/recommendation-agent-demo/recommendation-agent/recommendation-agent:v1
```

Подтверждённый digest образа:

```text
sha256:351ea0880a1ac64980991847f0a93fb8238e67a92bd237834e852d416486b909
```

### Изменение concurrency

Первоначально concurrency была установлена в 1. На мобильном устройстве наблюдалась ошибка загрузки JavaScript-модуля интерфейса; в логах также встречался HTTP 429.

После изменения concurrency на 80 была создана revision:

```text
recommendation-agent-00002-j5w
```

### Проверка конфигурации

Активная конфигурация gcloud:

```bash
gcloud config list
```

Описание сервиса:

```bash
gcloud run services describe recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

Список revisions:

```bash
gcloud run revisions list \
  --service=recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

Проверка публичного URL:

```bash
gcloud run services describe recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3 \
  --format="value(status.url)"
```

## 11. Публичная демонстрация и данные

Секреты, API-ключи, `.env` и учётные данные не должны попадать в образ или репозиторий.

## 12. Архитектурные ограничения

Не добавлять FastAPI, внешнюю БД, RAG, vector DB, микросервисы или multi-agent без конкретной блокирующей причины.

Не заявлять рост конверсии/выручки без подтверждённого эксперимента.

Не трактовать Fill Rate как метрику релевантности.

Не считать co-purchase доказательством технической совместимости.
