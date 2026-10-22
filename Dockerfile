FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRACKER_DATA_DIR=/app/data
WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY app ./app
RUN uv sync --no-dev --no-install-project

RUN mkdir -p /app/data && chown -R nobody:nogroup /app
USER nobody
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
