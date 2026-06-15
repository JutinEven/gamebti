FROM node:22-alpine AS frontend-build
WORKDIR /fe
COPY 前端网页/package.json 前端网页/package-lock.json ./
RUN npm ci
COPY 前端网页/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# Agent
COPY Agent/pyproject.toml Agent/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY Agent/src/ src/
COPY Agent/config/ config/
ENV PYTHONPATH=/app/src

# Frontend static files
COPY --from=frontend-build /fe/out /app/fe

ENV PORT=5000
EXPOSE 5000
CMD ["sh", "-c", "uv run python src/main.py -m http -p ${PORT:-5000}"]
