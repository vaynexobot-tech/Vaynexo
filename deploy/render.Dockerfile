# Render (yoki istalgan Docker hosting) uchun bitta konteyner: frontend + API + bot + fon ishlari (yengil rejim).
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FRONTEND_DIR=/app/static MEDIA_DIR=/app/media REDIS_URL=
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /app/static
RUN useradd -m app && mkdir -p /app/media && chown -R app /app
USER app
EXPOSE 10000
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
