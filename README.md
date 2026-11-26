# Recommendation Agent

MVP рекомендательной системы для личного кабинета B2B интернет-магазина.

## Назначение

Система формирует персонализированные рекомендации трёх типов:

- Cross-sell — дополняющие товары и услуги.
- Up-sell — расширенные или более подходящие решения.
- Renewal — продление лицензий и подписок.

## Текущий статус

Проект находится на этапе локальной разработки.

- [x] Подготовка Google Cloud
- [x] Выбор региона Cloud Run: `asia-southeast3`
- [x] Локальная среда Python
- [x] Демонстрационные данные
- [ ] Recommendation Engine
- [ ] Streamlit UI
- [ ] Тесты
- [ ] Docker
- [ ] Деплой в Cloud Run
- [ ] Проверка публичного демо

## Технологии

- Python 3.11+
- Streamlit
- JSON
- pytest
- Docker
- Google Cloud Run

LLM — опциональный компонент для улучшения текстовых объяснений рекомендаций.

## Локальный запуск

Клонирование репозитория и переход в его каталог:

```bash
git clone git@github.com:denis-42ds/recommendation-agent.git
cd recommendation-agent
```

Создание виртуального окружения:

```bash
python3 -m venv .venv
```

Активация окружения:

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Установка зависимостей:

```bash
python -m pip install -e ".[dev]"
```

Запуск:

```bash
streamlit run app.py
```

## Архитектура

Одно Streamlit-приложение, Python-модуль рекомендаций и JSON-файлы с демонстрационными данными.

Основной поток:

```text
Context
  -> Candidate Generation
  -> Business Filtering
  -> Ranking
  -> Explanation
  -> Recommendations
```

## Документация

- `docs/STATE.md` — актуальный статус проекта.
- `docs/requirements.md` — требования MVP.
- `docs/architecture.md` — архитектура и принятые технические решения.

## Данные

Для демонстрации используются синтетические данные. Реальные клиентские данные не добавлять без разрешения.

## Развёртывание

Целевая платформа — Google Cloud Run, регион `asia-southeast3`.

Подготовка Docker и инструкция по деплою будут добавлены после проверки локальной версии.

