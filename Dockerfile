FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev curl git \
    && rm -rf /var/lib/apt/lists/*

COPY bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD ["python3", "bot.py"]
