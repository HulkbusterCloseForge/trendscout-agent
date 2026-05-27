FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY backend ./backend
COPY static ./static
COPY scripts ./scripts
COPY samples ./samples

RUN pip install --upgrade pip \
    && pip install -e .

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/api/status >/dev/null || exit 1

CMD ["uvicorn", "trendcut_agent.app:app", "--host", "0.0.0.0", "--port", "8765"]
