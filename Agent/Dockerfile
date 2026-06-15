FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY src/ src/
COPY config/ config/
ENV PYTHONPATH=/app/src
EXPOSE 5000
CMD ["uv", "run", "python", "src/main.py", "-m", "http", "-p", "5000"]
