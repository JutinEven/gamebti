# Gamebti — combined Agent + static Frontend
# Stage 1: Build Frontend
FROM node:22-alpine AS frontend-build
WORKDIR /fe
COPY 前端网页/package.json 前端网页/package-lock.json ./
RUN npm ci
COPY 前端网页/ ./
RUN npm run build

# Stage 2: Agent + serve static
FROM python:3.12-slim
WORKDIR /app

COPY Agent/pyproject.toml Agent/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY Agent/src/ src/
COPY Agent/config/ config/
ENV PYTHONPATH=/app/src

COPY --from=frontend-build /fe/out /app/fe

EXPOSE 5000
CMD ["sh", "-c", "uv run python src/main.py -m http -p ${PORT:-5000}"]
