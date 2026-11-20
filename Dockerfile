FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 \
    BA_DATA_PATH=/app/data/processed/sales.parquet \
    BA_METADATA_PATH=/app/data/processed/metadata.json \
    BA_STATIC_DIR=/app/backend/static

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY data/processed /app/data/processed
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

