# Terramon TMA — Reflex full-stack on Railway
FROM python:3.13-slim

# System deps for Reflex (node/bun are fetched by reflex itself)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download frontend toolchain + compile at build time (faster cold start)
RUN reflex init --loglevel warning || true
RUN reflex export --frontend-only --no-zip --loglevel warning || true

# Railway provides $PORT. Reflex serves frontend + backend together in prod.
ENV PORT=8080
EXPOSE 8080

# Run both frontend (static, on $PORT) and backend (API/websocket).
CMD reflex run --env prod --backend-host 0.0.0.0 --backend-port ${PORT}
