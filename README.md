# Recommendation Agent

MVP рекомендательной системы для личного кабинета интернет-магазина Softline.

**Актуальность:** 27.11.2026
**Статус:** локальный MVP реализован; Docker-сборка и запуск подтверждены; приложение развёрнуто в Google Cloud Run.

## Цель и scope

Целевой продукт предусматривает три сценария:

- **Cross-sell** — дополняющие товары и услуги.
- **Up-sell** — расширенные или более подходящие решения.
- **Renewal** — продление лицензий и подписок.

**DECISION:** в хакатонном MVP реализуется Cross-sell. Up-sell и Renewal не входят в текущий scope.

## Текущий статус

| Область | Статус | Подтверждение |
|---|---|---|
| Baseline / backtest | DONE | Когорты совпали с организаторами; Popularity совпадает |
| Co-purchase comparison | PARTIALLY DONE | Есть расхождения с официальными цифрами; требуется отдельный анализ |
| Catalog builder | DONE WITH LIMITATIONS | 438 matched `item_id` из 817; 379 unmatched |
| Product graph | DONE | 813 узлов, 1 986 рёбер |
| Recommendation Engine | DONE | Локальные smoke и диагностическая оценка выполнены |
| Automated checks | DONE | Ruff, `git diff --check`, 45 тестов прошли |
| Streamlit UI | DONE | Локальный запуск и функциональность подтверждены |
| Docker | DONE | Сборка образа и запуск контейнера подтверждены |
| Cloud Run | DEPLOYED | Сервис Ready, публичный URL доступен |

## Публичная демонстрация

Приложение развёрнуто в Google Cloud Run.

- **URL:** https://recommendation-agent-ug7evithwa-eu.a.run.app
- **Google Cloud project:** `recommendation-agent-demo`
- **Cloud Run service:** `recommendation-agent`
- **Region:** `asia-southeast3` (Bangkok)
- **Последняя подтверждённая revision:** `recommendation-agent-00002-j5w`
- **Traffic:** 100% на revision `recommendation-agent-00002-j5w`
- **Concurrency:** 80
- **Container image:**

```text
asia-southeast3-docker.pkg.dev/recommendation-agent-demo/recommendation-agent/recommendation-agent:v1
```

## Архитектура

Модульный монолит: Streamlit UI, Recommendation Engine и загрузчик подготовленных артефактов в одном Python-приложении.

```text
Streamlit UI
    |
    v
Customer Context
    |
    v
Candidate Generation
    |-- Co-purchase
    `-- Popularity fallback
    |
    v
Business Filtering
    |-- исключить уже купленные product_group
    |-- оставить доступные предложения каталога
    `-- одна рекомендация на product_group
    |
    v
Ranking / Scoring
    |
    v
Evidence-based Explanation
    |
    v
Top-3
```

- Базовая функциональность работает без LLM.
- B2B и B2C обрабатываются раздельно.
- Для B2C запрещено использовать `industry` и корпоративный профиль клиента.
- Co-purchase означает совместную покупку в корзине, а не техническую совместимость.
- `product_id` в выдаче — `offer_id` каталога.
- Для cold-start используется popularity соответствующего сегмента.

## Локальный запуск

Требуются Python 3.11+ и подготовленные файлы данных/артефактов проекта.

Создание окружения:

```bash
python3 -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Установка:

```bash
python -m pip install -e ".[dev]"
```

Запуск UI:

```bash
streamlit run app.py
```

Проверки:

```bash
ruff check
python -m pytest -q
git diff --check
```

Дополнительные проверки движка:

```bash
python -m scripts.check_recommendation_engine
python -m scripts.evaluate_recommendation_engine
```

Диагностический скрипт формирует `artifacts/evaluation/engine_quality.json`.

## Docker

Сборка:

```bash
docker build -t recommendation-agent:local .
```

Запуск:

```bash
docker run --rm -p 8080:8080 recommendation-agent:local
```

После запуска приложение доступно:

```text
http://localhost:8080
```

## Google Cloud Run

Используется отдельная конфигурация gcloud `recommendation-agent`.

Проверить активную конфигурацию:

```bash
gcloud config list
```

Проверить состояние сервиса:

```bash
gcloud run services describe recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

Проверить revisions:

```bash
gcloud run revisions list \
  --service=recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

Проверить URL:

```bash
gcloud run services describe recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3 \
  --format="value(status.url)"
```

Регион `asia-southeast3` соответствует Bangkok.

## Данные и артефакты

| Артефакт | Назначение |
|---|---|
| `artifacts/product_graph/graph.json` | Граф совместных покупок, построенный по Train |
| `artifacts/catalog/matched_products.json` | Сопоставленные предложения каталога |
| `artifacts/catalog/item_mapping.json` | Результат сопоставления `item_id` с предложениями |
| `artifacts/evaluation/engine_quality.json` | Диагностика Fill Rate и состава рекомендаций |
| `artifacts/baseline/` | Результаты baseline/backtest |

## Данные и публичная демонстрация

Не публиковать секреты, ключи, `.env` и иные чувствительные данные.

## Ограничения

- Up-sell и Renewal не реализованы.
- Интеграция с реальным личным кабинетом Softline не подтверждена.
- Обратная связь по кликам и показам рекомендаций не реализована.
- Онлайн-эксперимент и оценка влияния на конверсию/выручку не проводились.
- Исторические snapshots каталога и профилей отсутствуют.
- Сопоставление каталога неполное: 438 из 817 sales `item_id` сопоставлены в последнем подтверждённом запуске.
- Co-purchase не доказывает техническую совместимость товаров.
- Цена не отображается: соответствующего поля в модели `ProductOffer` нет.
- Fill Rate 100% характеризует заполненность позиций, а не релевантность рекомендаций.
- Не заявлять рост конверсии или выручки без подтверждённого эксперимента.

## Документация

- `docs/STATE.md` — текущее состояние и подтверждённые результаты.
- `docs/requirements.md` — scope и критерии MVP.
- `docs/architecture.md` — компоненты и поток обработки.
- `docs/SUBMISSION.md` — материалы для формы подачи.
- `docs/THIRD_PARTY_LICENSES.md` — перечень сторонних компонентов и лицензий.
- `docs/decisions/ADR-002-product-graph.md` — отдельный граф совместных покупок.
- `docs/decisions/ADR-003-baseline-v5.md` — протокол baseline v5 и роль `product_group`.
- `docs/decisions/ADR-008-mvp-scope-freeze.md` — фиксация scope.
- `docs/decisions/ADR-009-engine-product-deduplication.md` — идентичность товара в движке.
- `docs/DEMO_SCRIPT.md` — сценарий записи демонстрации.
