# Recommendation Agent

MVP рекомендательной системы для личного кабинета интернет-магазина Softline.

**Актуальность:** 27.11.2026

## Цель и scope

Целевой продукт предусматривает три сценария:
- **Cross-sell** — дополняющие товары и услуги.
- **Up-sell** — расширенные или более подходящие решения.
- **Renewal** — продление лицензий и подписок.

**DECISION:** в хакатонном MVP реализуется Cross-sell. Up-sell и Renewal не расширяют текущий scope.

## Текущий статус

| Область | Статус | Подтверждение |
|---|---|---|
| Baseline / backtest | DONE | Когорты совпали с организаторами; Popularity совпадает |
| Co-purchase comparison | PARTIALLY DONE | Есть расхождения с официальными цифрами; нужен отдельный анализ |
| Catalog builder | DONE WITH LIMITATIONS | 438 matched item_id из 817; 379 unmatched |
| Product graph | DONE | 813 узлов, 1 986 рёбер |
| Recommendation Engine | DONE (локально) | Smoke и диагностическая оценка выполнены пользователем |
| Automated checks | DONE | `ruff check`, `git diff --check`, 45 тестов прошли |
| Streamlit UI | DONE (локально) | Пользователь подтвердил запуск и доступность функций |
| Docker | OPEN | Сборка и запуск не подтверждены |
| Cloud Run | OPEN | Публичный деплой и smoke test не подтверждены |

Не считать локальную готовность подтверждением публичного деплоя.

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
- Для B2C запрещено использовать `industry` и корпоративный профиль.
- Co-purchase означает совместную покупку в корзине, а не техническую совместимость.
- `product_id` в выдаче — `offer_id` каталога.

## Локальный запуск

Требуются Python 3.11+ и подготовленные файлы данных/артефактов проекта.

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

## Данные и артефакты

| Артефакт | Назначение |
|---|---|
| `artifacts/product_graph/graph.json` | Граф совместных покупок, построенный по Train |
| `artifacts/catalog/matched_products.json` | Сопоставленные предложения каталога |
| `artifacts/catalog/item_mapping.json` | Результат сопоставления `item_id` с предложениями |
| `artifacts/evaluation/engine_quality.json` | Диагностика Fill Rate и состава рекомендаций |
| `artifacts/baseline/` | Результаты baseline/backtest |

Точные входные файлы датасета должны оставаться в локальном окружении, если их публикация не разрешена.

## Ограничения и безопасность

- Не публиковать исходный датасет, клиентские данные и персональные сведения.
- Для публичной демонстрации использовать синтетические или обезличенные данные.
- Не выдумывать SKU, цену, наличие, сроки лицензии или совместимость.
- Исторические snapshots каталога и профилей отсутствуют; текущие сведения о каталоге не являются историческим состоянием на дату покупки.
- Не заявлять рост конверсии или выручки без подтверждённого эксперимента.

## Документация

- `docs/STATE.md` — текущее состояние и подтверждённые результаты.
- `docs/requirements.md` — scope и критерии MVP.
- `docs/architecture.md` — компоненты и поток обработки.
- `docs/decisions/ADR-002-product-graph.md` — отдельный граф совместных покупок.
- `docs/decisions/ADR-003-baseline-v5.md` — протокол baseline v5 и роль `product_group`.
- `docs/decisions/ADR-008-mvp-scope-freeze.md` — фиксация scope.
- `docs/decisions/ADR-009-engine-product-deduplication.md` — идентичность товара в движке.
- `docs/DEMO_SCRIPT.md` — сценарий записи демонстрации.
