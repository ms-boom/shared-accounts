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

# Install dependencies (cached layer — rebuilds only when lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Install Patchright browser (cached layer — rebuilds only when patchright version changes)
RUN uv run patchright install chrome && \
    uv run patchright install-deps

# Copy project source code (changes here don't rebuild layers above)
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY README.md ./

# Install the project itself (fast — dependencies already cached)
RUN uv sync --frozen

# Create data directories
RUN mkdir -p /data/sessions /data/logs /data/errors && \
    chmod 700 /data/sessions

COPY entrypoint.sh ./
CMD ["./entrypoint.sh"]
