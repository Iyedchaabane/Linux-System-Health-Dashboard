FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/README.md ./README.md
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src

RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src

USER 65532
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/healthz'); sys.exit(0)" || exit 1

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "monitor.presentation.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
