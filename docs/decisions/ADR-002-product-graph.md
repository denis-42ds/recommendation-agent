Фиксируем принятое решение
DECISION
 Product Graph — отдельная функциональность, не часть baseline.
Вопрос	Принятое решение
Baseline	Не изменяем scripts/run_baseline.py
Источник данных	Исходный Excel Датасет_Рекомендации_ЛК_v3.xlsx
Период	Только Train: order_week <= 2026-08-31
Test	Полностью исключён из построения графа
Узлы	item_id
Рёбра	Пары товаров, встречающиеся в одном заказе
Вес ребра	Количество уникальных заказов с этой парой
Тип графа	Неориентированный, без самосвязей
Скрипт	scripts/build_product_graph.py
Результаты	artifacts/product_graph/

Структура:

```text
scripts/
├── run_baseline.py
└── build_product_graph.py

artifacts/
├── baseline/
│   ├── baseline_metrics.csv
│   ├── cohort_sizes.csv
│   ├── predictions_by_client.csv
│   ├── precision_at_3.png
│   ├── fill_rate.png
│   └── cohort_sizes.png
│
└── product_graph/
    ├── nodes.csv
    ├── edges.csv
    └── graph.json
```
