# Terramon TMA — Reflex full-stack on Railway
FROM python:3.13-slim

# System deps for Reflex (node/bun are fetched by reflex itself)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade reflex reflex-base

COPY . .

# Force full frontend recompile — delete any cached .web from prior builds
RUN rm -rf .web

# Init with debug logging so Railway build logs show where errors happen
RUN reflex init --loglevel debug

# Export frontend to static files (faster cold start, no zip archive)
RUN reflex export --frontend-only --no-zip --loglevel debug

# Railway provides $PORT. Reflex serves frontend + backend together in prod.
ENV PORT=8080
EXPOSE 8080

# Run both frontend (static, on $PORT) and backend (API/websocket).
CMD reflex run --env prod --backend-host 0.0.0.0 --backend-port ${PORT}
