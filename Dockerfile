FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app \
    HOME=/tmp/app-home \
    XDG_CONFIG_HOME=/tmp/app-home/.config \
    STREAMLIT_CONFIG_DIR=/tmp/app-home/.streamlit \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    MPLCONFIGDIR=/tmp/app-home/.config/matplotlib

WORKDIR /app

RUN mkdir -p \
    /tmp/app-home/.config/matplotlib \
    /tmp/app-home/.streamlit \
    && chmod -R 777 /tmp/app-home

RUN groupadd --system app && useradd --system --gid app app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

COPY app.py ./
COPY scripts/run_baseline.py ./scripts/run_baseline.py

COPY artifacts/product_graph/graph.json ./artifacts/product_graph/graph.json
COPY artifacts/catalog/matched_products.json ./artifacts/catalog/matched_products.json
COPY docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx ./docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx

RUN chown -R app:app /app
USER app

EXPOSE 8080

CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080}"]
