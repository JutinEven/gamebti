FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml .

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic python-dotenv \
    langchain langchain-openai langgraph langgraph-checkpoint \
    duckduckgo-search httpx \
    pypdf docx2python openpyxl python-pptx pandas

# 复制源码
COPY src/ src/
COPY config/ config/

# 环境变量
ENV PYTHONPATH=/app/src
ENV PORT=8080

# 启动
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
