FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock .python-version /app/
COPY src /app/src
COPY migrations /app/migrations
COPY config /app/config

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "pfp-mcp"]
