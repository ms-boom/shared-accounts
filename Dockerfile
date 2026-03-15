FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (browser libs + xvfb for headed mode)
RUN apt-get update && apt-get install -y \
    git \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Install dependencies
RUN uv sync --frozen

# Install Patchright browser (Chrome for better stealth)
RUN uv run patchright install chrome
RUN uv run patchright install-deps

# Create data directories
RUN mkdir -p /data/sessions /data/logs /data/errors && \
    chmod 700 /data/sessions

COPY entrypoint.sh ./
CMD ["./entrypoint.sh"]
