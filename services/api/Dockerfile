FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md TESTING.md ./
COPY gengscope_api ./gengscope_api

RUN pip install --no-cache-dir ".[postgres]"

EXPOSE 8000

CMD ["gengscope-api", "--host", "0.0.0.0", "--port", "8000"]
