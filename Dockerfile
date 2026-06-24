FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=3090 \
    RUN_SERVER=1 \
    DBC_CONFIGURATION_FILE=/app/configuration/service_config.json

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY ms_database_connector ./ms_database_connector

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir .

COPY configuration ./configuration

EXPOSE 3090

CMD ["python", "-m", "ms_database_connector"]
