FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g npx

# --- Agent ---
COPY Agent/pyproject.toml Agent/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY Agent/src/ src/
COPY Agent/config/ config/
ENV PYTHONPATH=/app/src

# --- Frontend ---
COPY 前端网页/ fe/
WORKDIR /app/fe
RUN npm install
RUN npm run build || true
WORKDIR /app

# --- Start both ---
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'cd /app && uv run python src/main.py -m http -p ${PORT:-5000} &' >> /app/start.sh && \
    echo 'cd /app/fe && npx next dev -p 3000 &' >> /app/start.sh && \
    echo 'wait' >> /app/start.sh && \
    chmod +x /app/start.sh

# Update frontend to call Agent on localhost
RUN echo 'AGENT_BASE_URL=http://localhost:5000' > /app/fe/.env.local

ENV PORT=5000
EXPOSE 5000 3000
CMD ["/app/start.sh"]
