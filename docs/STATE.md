# STATE — Recommendation Agent

**Дата обновления:** 27.11.2026
**Статус:** локальный MVP реализован; Docker build/run подтверждены; приложение развёрнуто в Google Cloud Run и доступно по публичному URL.

## 1. Цель

Создать демонстрируемый Recommendation Agent для личного кабинета интернет-магазина Softline.

Целевой продукт включает Cross-sell, Up-sell и Renewal; текущий MVP ограничен Cross-sell.

Критерии MVP:

1. Приложение запускается локально и в контейнере.
2. Можно выбрать B2B/B2C и демонстрационного клиента, включая клиента без истории.
3. Движок возвращает до трёх допустимых рекомендаций.
4. Результат содержит `product_id`, `recommendation_type`, `score`, `reason_codes`, `evidence`, `explanation`.
5. Товары принадлежат используемому каталогу; уже купленные товарные группы исключаются.
6. Базовая логика работает без LLM.
7. Приложение доступно через публичный Cloud Run URL.

## 2. Сводный статус

| Область | Статус | Основание |
|---|---|---|
| Google Cloud / gcloud | CONFIRMED | Пользователь подтвердил настройку |
| Cloud Run region | CONFIRMED | `asia-southeast3` (Bangkok) |
| Baseline / backtest | DONE | Когорты и Popularity совпали с официальными |
| Co-purchase comparison | PARTIALLY DONE | Известны расхождения, причина не установлена |
| Catalog builder | DONE WITH LIMITATIONS | 817 sales `item_id`; 438 matched; 379 unmatched |
| Product graph | DONE | 813 nodes, 1 986 edges |
| Recommendation Engine | DONE | Smoke и диагностический прогон выполнены пользователем |
| Automated checks | CONFIRMED | Ruff и diff check OK; 45 тестов прошли |
| Streamlit UI | CONFIRMED | Локальный запуск и функции подтверждены |
| Docker | CONFIRMED | Сборка и запуск контейнера подтверждены |
| Cloud Run deployment | CONFIRMED | Сервис Ready, публичный URL доступен |
| Cloud Run revision | CONFIRMED | `recommendation-agent-00002-j5w`, 100% traffic |
| Cloud Run concurrency | CONFIRMED | 80 |
| Desktop public smoke test | CONFIRMED | Пользователь подтвердил работу в браузере на компьютере |
| Mobile public smoke test | DONE | Пользователь подтвердил работу на мобильном устройстве |

Последний известный результат тестов:

```text
All checks passed!
45 passed
```

Пользователь подтвердил локальный запуск UI и доступность его функций.

## 3. Данные и артефакты

### Каталог

Последний подтверждённый результат построения каталога:

- `sales_item_count`: 817
- `feed_offer_count`: 135 952
- `matched_offer_count`: 552
- `matched_item_count`: 438
- `multi_offer_item_count`: 52
- `ambiguous_item_count`: 0
- `ambiguous_source_count`: 0
- `unmatched_item_count`: 379
- `match_rate`: 0.5361
- методы: `exact_name` 3, `URL article` 31, `vendorCode` 404.

`matched_products.json` содержит 552 записи. В них 548 уникальных `offer_id`; 526 предложений доступны и 26 недоступны. Четыре `offer_id` встречаются у двух `item_id`.

Ограничения:

- Каталог сопоставлен не полностью.
- Исторического snapshot наличия нет.
- Не расширять исследование matching без конкретной блокирующей диагностики.
- В выдачу движка попадают только доступные предложения, загруженные как `ProductOffer.available is True`.

### Граф

`artifacts/product_graph/graph.json`:

- schema version 2;
- Train end: `2026-08-31`;
- 813 nodes;
- 1 986 edges;
- неориентированный граф;
- корзина определяется ключом `(order_id, order_week)`.

Граф отражает совместные покупки, а не техническую совместимость. Узлы и рёбра остаются на уровне `item_id`.

### Особенность идентификаторов

Два исходных `item_id` для Sobol-4 PCIe A7 FSTEC-NORNG-SP1Y отличаются NBSP и обычным пробелом, но имеют одинаковое нормализованное значение и `product_group=G42011`.

Исходные `item_id` сохраняются в baseline и графе. В движке выдача дедуплицируется по `product_group`.

## 4. Backtest — неизменяемый протокол

- Train: `order_week <= 2026-08-31`.
- Test: `order_week >= 2026-09-07`.
- Цель: новые `item_id` в Test, отсутствовавшие в Train.
- Basket key: `(order_id, order_week)`.
- Cohort A: клиенты с покупками в Train и минимум одним новым товаром в Test.
- Cohort B: подмножество A с ровно одним уникальным товаром в Train.
- Precision@3: делитель всегда 3.
- B2B и B2C оцениваются раздельно.
- Popularity: число уникальных клиентов, купивших item в Train.
- Co-purchase: число Train-корзин, содержащих пару товаров; score суммирует pair counters по истории клиента.
- Tie-break: score, popularity, `item_id` по алфавиту.

Официальные результаты организаторов:

| Метод / когорта | ALL | B2B | B2C | Fill Rate |
|---|---:|---:|---:|---:|
| Popularity A | 5.2% | 3.6% | 19.4% | 100% |
| Popularity B | 7.0% | 5.1% | 19.2% | 100% |
| Co-purchase A | 4.8% | 3.9% | 13.0% | 89% |
| Co-purchase B | 5.1% | 3.8% | 12.8% | 82% |

Локальные результаты пользователя:

| Когорта | Сегмент | Метод | Клиенты | Precision@3 | Fill Rate |
|---|---|---|---:|---:|---:|
| A | ALL | Co-purchase | 337 | 5.64% | 92.28% |
| A | ALL | Popularity | 337 | 5.44% | 100.00% |
| A | B2B | Co-purchase | 302 | 4.53% | 91.39% |
| A | B2B | Popularity | 302 | 3.75% | 100.00% |
| A | B2C | Co-purchase | 35 | 15.24% | 100.00% |
| A | B2C | Popularity | 35 | 20.00% | 100.00% |
| B | ALL | Co-purchase | 172 | 6.01% | 87.21% |
| B | ALL | Popularity | 172 | 7.36% | 100.00% |
| B | B2B | Co-purchase | 147 | 4.54% | 85.03% |
| B | B2B | Popularity | 147 | 5.22% | 100.00% |
| B | B2C | Co-purchase | 25 | 14.67% | 100.00% |
| B | B2C | Popularity | 25 | 20.00% | 100.00% |

**CONFIRMED:** размеры когорт совпали; Popularity совпадает с официальным результатом в рамках принятого округления.

**OPEN:** Co-purchase расходится с результатами организаторов. Это требует отдельного анализа и не доказывает автоматически ошибку реализации. Не менять протокол ради совпадения метрик.

## 5. Recommendation Engine

Реализованный локальный поток:

1. История клиента передаётся как `item_id`.
2. Co-purchase кандидаты извлекаются из графа.
3. Источники кандидатов агрегируются.
4. Уже купленные `product_group` исключаются.
5. Кандидаты без доступного предложения каталога исключаются.
6. Для каждой `product_group` выбирается одно доступное предложение.
7. Co-purchase используется первым; Popularity сегмента — для заполнения оставшихся слотов.
8. При cold-start используется popularity и результат помечается как неперсонализированный.

`product_id` результата — `offer_id`. Выбор предложения внутри группы детерминирован по `(offer_id, item_id)`.

Popularity движка агрегируется на уровне `product_group` по числу уникальных клиентов в Train и отдельно для сегментов. B2C не использует `industry` или корпоративный профиль.

### Диагностика движка

Подтверждённый пользователем прогон:

- всего клиентов: 19 008;
- с историей: 17 457;
- без истории: 1 551;
- неподдерживаемых сегментов: 0;
- оценено клиентов: 19 008;
- B2B: 9 739 клиентов; с историей 9 018; cold-start 721;
- B2C: 9 269 клиентов; с историей 8 439; cold-start 830;
- Fill Rate: 100% для ALL, B2B и B2C;
- Top-3 заполнен у всех клиентов в этом прогоне.

Состав 57 024 рекомендательных позиций:

- co-purchase: 40 468;
- popularity fallback: 11 903;
- cold-start popularity: 4 653.

Для клиентов с историей 52 371 позиции: 77.3% co-purchase и 22.7% popularity fallback. Это доли рекомендательных позиций, не доли клиентов и не Precision@3.

**Важно:** Fill Rate показывает заполненность слотов, а не релевантность рекомендаций. Эти цифры не доказывают рост конверсии или выручки.

## 6. Проверки и локальный запуск

Подтверждено пользователем:

```bash
git diff --check
ruff check
python -m pytest -q
python -m scripts.check_recommendation_engine
python -m scripts.evaluate_recommendation_engine
streamlit run app.py
```

Результат тестов: 45 passed.

Docker build/run подтверждены:

```bash
docker build -t recommendation-agent:local .
docker run --rm -p 8080:8080 recommendation-agent:local
```

Пользователь подтвердил отображение UI на `http://localhost:8080` и отсутствие ошибок приложения в терминале.

Последний известный статус git в более раннем запуске показывал незатреканные `app.py` и `scripts/evaluate_recommendation_engine.py`. Не считать файлы закоммиченными без актуального `git status`.

## 7. Cloud Run deployment

### Подтверждённые параметры

| Параметр | Значение |
|---|---|
| Google Cloud project | `recommendation-agent-demo` |
| Cloud Run service | `recommendation-agent` |
| Region | `asia-southeast3` (Bangkok) |
| Public URL | https://recommendation-agent-ug7evithwa-eu.a.run.app |
| Последняя подтверждённая revision | `recommendation-agent-00002-j5w` |
| Traffic | 100% на `recommendation-agent-00002-j5w` |
| Concurrency | 80 |
| Artifact Registry repository | `recommendation-agent` |
| Artifact Registry location | `asia-southeast3` |

Container image:

```text
asia-southeast3-docker.pkg.dev/recommendation-agent-demo/recommendation-agent/recommendation-agent:v1
```

Подтверждённый digest:

```text
sha256:351ea0880a1ac64980991847f0a93fb8238e67a92bd237834e852d416486b909
```

### История изменения concurrency

Первоначально concurrency была установлена в 1.

На мобильном устройстве наблюдалась ошибка:

```text
TypeError: Failed to fetch dynamically imported module
```

В логах встречались успешные GET 200 и один GET 429.

Пользователь выполнил:

```bash
gcloud run services update recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3 \
  --concurrency=80
```

Создана revision `recommendation-agent-00002-j5w`, на неё направлено 100% трафика.

Пользователь сообщил, что проблемы, по-видимому, исчезли.

### Команды проверки

```bash
gcloud config list
```

```bash
gcloud run services describe recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

```bash
gcloud run revisions list \
  --service=recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3
```

```bash
gcloud run services logs read recommendation-agent \
  --project=recommendation-agent-demo \
  --region=asia-southeast3 \
  --limit=100
```

CPU, memory, min/max instances и актуальные настройки autoscaling не зафиксированы: требуется сверить текущий вывод `describe`.

## 8. Решения и ограничения

- Cross-sell first; не расширять scope на Up-sell/Renewal.
- Baseline и граф сохраняют `item_id`; движок дедуплицирует рекомендации по `product_group`.
- `product_id=offer_id`.
- LLM не находится в критическом пути.
- B2C не использует `industry` и корпоративный профиль.
- Co-purchase не является доказательством технической совместимости.
- Не показывать цену: соответствующего поля в модели `ProductOffer` нет.
- Исторические snapshots каталога и профилей отсутствуют.
- Каталог сопоставлен не полностью.
- Не заявлять рост бизнес-метрик без эксперимента.

### Публичная демонстрация данных

Секреты, ключи и `.env` не включать в репозиторий и Docker-образ.

## 9. Следующие действия

### Перед сдачей

1. Открыть публичный URL на компьютере и пройти полный сценарий демонстрации.
2. Повторить smoke test на мобильном устройстве после изменения concurrency на 80.
3. Проверить актуальную revision и 100% traffic через `gcloud run revisions list`.
4. Проверить текущие CPU, memory, min/max instances через `gcloud run services describe`.
5. Проверить Cloud Run logs на ошибки после контрольного прогона.
6. Обновить и проверить `docs/SUBMISSION.md`.
7. Получить фактический перечень лицензий прямых и транзитивных зависимостей.
8. Проверить `git status`, `git diff --check` и состав публичного репозитория.
9. Подготовить и записать трёхминутную демонстрацию.

### После сдачи / при наличии времени

1. Отдельно исследовать расхождения Co-purchase, не меняя backtest protocol.
2. Рассмотреть фиксацию зависимостей lock-файлом.
3. Оценить покрытие каталога только при наличии конкретной блокирующей проблемы.
4. Планировать Up-sell/Renewal отдельно от текущего MVP.

## 10. Правило достоверности

`DONE/CONFIRMED` ставить только после локального результата или явного подтверждения пользователя.

ChatGPT не запускает локальный код, тесты, backtest и расчёты. Все команды исполняет разработчик.

При отсутствии подтверждения использовать `OPEN`, а не выдавать предположение за факт.
