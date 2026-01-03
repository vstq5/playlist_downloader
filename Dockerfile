# --- Stage 1: Build Frontend ---
# NOTE: Use Debian-based Node image (glibc). Alpine (musl) can break native deps like lightningcss.
FROM node:18-bullseye-slim AS frontend-builder
WORKDIR /app/web
COPY web/package.json ./
RUN npm install --include=optional
COPY web/ .
RUN npm run build

# --- Stage 2: Build Backend ---
FROM python:3.11-slim AS backend
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Persistent storage for downloads (even ephemeral in free tier)
RUN mkdir -p /app/static/downloads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Copy Frontend
COPY --from=frontend-builder /app/web/dist /app/static

ENV PYTHONPATH=/app/src

# Render sets $PORT dynamically; keep a sensible local default.
# Proxy headers are required behind Render/Vercel so client IP is not the proxy.
CMD ["sh", "-c", "uvicorn src.playlist_downloader.server:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
