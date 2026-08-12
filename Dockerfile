# =============================================================================
# Terramon TMA — Multi-stage Docker build
# =============================================================================
# Phase 0 audit fix: uses multi-stage build, non-root user, layer caching,
# combined RUN layers, and minimal final image.
# =============================================================================

# ── Stage 1: Build frontend ────────────────────────────────────────────
FROM python:3.13-slim AS builder

# System deps for Reflex (node/bun are fetched by reflex itself)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only dependency files first — leverages Docker layer caching so
# pip install only re-runs when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade reflex reflex-base

# Now copy the full source
COPY . .

# Force full frontend recompile — delete any cached .web from prior builds
RUN rm -rf .web

# Init with debug logging so Railway build logs show where errors happen
RUN reflex init --loglevel debug

# Export frontend to static files (faster cold start, no zip archive)
RUN reflex export --frontend-only --no-zip --loglevel debug

# ── Stage 2: Runtime ──────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Runtime needs unzip too: reflex run may re-validate frontend deps at
# startup and falls back to installing bun itself if the copied binary
# is missing or the version check fails (lesson: build stage tools !=
# runtime stage tools is a classic Docker drift bug).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy the bun binary fetched during build so runtime never re-downloads it.
# REFLEX_USE_SYSTEM_BUN=true makes Reflex use `which bun` (PATH) instead of
# its own $REFLEX_DIR/bun — deterministic, no network at startup.
COPY --from=builder /root/.local/share/reflex/bun/bin/bun /usr/local/bin/bun
ENV REFLEX_USE_SYSTEM_BUN=true

# Create a non-root user for security
RUN groupadd -r terramon && \
    useradd -r -g terramon -d /app -s /sbin/nologin terramon && \
    mkdir -p /app && \
    chown terramon:terramon /app

WORKDIR /app

# Copy Python dependencies from builder (same slim image = binary compatible)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application source + pre-built frontend
COPY --from=builder /app /app

# Ensure .web directory is writable by the non-root user
# Also pre-create stateful_pages.json so Reflex doesn't try to create it at runtime
# REFLEX_DIR (/app/.local/share/reflex) must exist + be writable: non-root reflex
# writes logs/config there on startup (verified via platformdirs resolution).
# reflex.lock/ is created by the build stage as root; the runtime user must own it
# because `reflex run` syncs the canonical bun.lock there on every start
# (reflex-dev/reflex #6475 — lockfile moved under reflex.lock/).
RUN mkdir -p /app/data /app/.web/backend /app/.local/share/reflex /app/reflex.lock && \
    touch /app/.web/backend/stateful_pages.json && \
    chown -R terramon:terramon /app/data /app/.web/backend/stateful_pages.json /app/.web /app/.local/share/reflex /app/reflex.lock

# Container starts as root so startup.sh can fix Railway volume ownership
# (volumes mount root-owned at container start; a non-root user cannot
# chmod/chown them — that was the crash loop). startup.sh drops privileges
# back to terramon before exec'ing the app.
USER root

# Railway provides $PORT. Reflex serves frontend + backend together in prod.
ENV PORT=8080
EXPOSE 8080

# Docker-native healthcheck (Phase 17: MLOps) — pings the Reflex /health
# endpoint every 30s. The REFLEX backend must expose this route (see
# terramon_tma.py health() page).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://127.0.0.1:${PORT}/health || exit 1

# Run cleanup of old portrait files on startup (30-day retention).
# Phase 17: prevents unbounded disk growth from generated images.
RUN echo '#!/bin/sh\n\
\necho "[startup] Ensuring /app/data writable (Railway volume)"\n\
chmod -R 777 /app/data 2>/dev/null || true\n\
chown -R terramon:terramon /app/data 2>/dev/null || true\n\
find /app/data/creatures -name "*.png" -type f -mtime +30 -delete 2>/dev/null || true\n\
find /app/data/creatures/thumbnails -name "*.png" -type f -mtime +30 -delete 2>/dev/null || true\n\
find /app/data/creatures/placeholders -name "*.png" -type f -mtime +30 -delete 2>/dev/null || true\n\
\necho "[startup] Cleaned portraits older than 30 days"\n\
if [ "$(id -u)" = "0" ]; then\n\
  exec setpriv --reuid=terramon --regid=terramon --init-groups "$@" 2>/dev/null || exec su terramon -s /bin/sh -c "$*"\n\
fi\n\
exec "$@"' > /app/startup.sh && chmod +x /app/startup.sh

# Run both frontend (static, on $PORT) and backend (API/websocket).
CMD /app/startup.sh reflex run --env prod --backend-host 0.0.0.0 --backend-port ${PORT:-8080}
