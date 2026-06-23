FROM node:22-alpine AS frontend-build
WORKDIR /fe
COPY 前端网页/package.json 前端网页/package-lock.json ./
RUN npm ci
COPY 前端网页/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY Agent/pyproject.toml Agent/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --no-dev
COPY Agent/src/ src/
COPY Agent/config/ config/
ENV PYTHONPATH=/app/src

# LLM 提供商和模型（API Key 请在 Railway Variables 中设置，不要硬编码！）
ENV LLM_PROVIDER=deepseek
ENV LLM_MODEL=deepseek-chat
# ITAD_API_KEY 请在 Railway Variables 中设置

COPY --from=frontend-build /fe/out /app/fe
EXPOSE 5000
CMD [".venv/bin/python", "src/main.py", "-m", "http", "-p", "5000"]
