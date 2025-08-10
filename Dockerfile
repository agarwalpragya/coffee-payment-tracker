# Multi-stage build: build React UI, then serve Flask + static dist via Gunicorn

# ---------- Stage 1: Frontend build ----------
FROM node:20-alpine AS fe-build
WORKDIR /app/frontend

# Copy minimal files first to maximize Docker layer caching for installs
COPY frontend/package.json frontend/vite.config.js frontend/index.html ./
# App source
COPY frontend/src ./src
COPY frontend/public ./public

# Install deps & build
RUN npm ci || npm install
RUN npm run build

# ---------- Stage 2: Backend runtime ----------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# (Optional) certs for TLS outbounds, then cleanup apt lists to keep image slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY backend /app/backend

# Copy built frontend into /app/frontend/dist
RUN mkdir -p /app/frontend/dist
COPY --from=fe-build /app/frontend/dist /app/frontend/dist

# Install Python deps and Gunicorn
RUN pip install --no-cache-dir -r backend/requirements.txt gunicorn==22.0.0

EXPOSE 5000

# Serve Flask app via Gunicorn
CMD ["gunicorn", "app:app", "--chdir", "backend", "-b", "0.0.0.0:5000", "--workers", "2"]
