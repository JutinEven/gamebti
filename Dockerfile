FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY Agent/pyproject.toml Agent/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

COPY Agent/src/ src/
COPY Agent/config/ config/
ENV PYTHONPATH=/app/src

EXPOSE 5000
CMD ["sh", "-c", "uv run python src/main.py -m http -p ${PORT:-5000}"]
