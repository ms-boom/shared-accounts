FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY bot/ ./bot/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Install dependencies
RUN uv sync --frozen

# Create data directories
RUN mkdir -p /data/sessions /data/logs /data/errors && \
    chmod 700 /data/sessions

# Run bot
CMD ["uv", "run", "python", "-m", "bot"]
