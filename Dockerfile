FROM python:3.12-slim

WORKDIR /app

# Create non-root user early so all files are owned by bot from the start
RUN groupadd --gid 1000 bot && \
    useradd --uid 1000 --gid bot --shell /bin/bash --create-home bot && \
    chown bot:bot /app

# Install system packages (root required for apt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    ca-certificates \
    fonts-liberation \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Switch to bot user — all subsequent files owned by bot
USER bot

# Install dependencies (cached layer — rebuilds only when lock changes)
COPY --chown=bot:bot pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Install Patchright browser + system deps, clean caches in one layer
USER root
RUN .venv/bin/patchright install chrome && \
    .venv/bin/patchright install-deps && \
    rm -rf /root/.cache /tmp/* /var/lib/apt/lists/*
USER bot

# Copy project source code (changes here don't rebuild layers above)
COPY --chown=bot:bot src/ ./src/
COPY --chown=bot:bot migrations/ ./migrations/
COPY --chown=bot:bot alembic.ini ./
COPY --chown=bot:bot README.md ./

# Install the project itself (fast — dependencies already cached)
RUN uv sync --frozen

# Create data directories and Xvfb socket dir (root needed for /data and /tmp)
USER root
RUN mkdir -p /data/sessions /data/logs /data/errors /tmp/.X11-unix && \
    chown -R bot:bot /data && \
    chmod 700 /data/sessions && \
    chmod 1777 /tmp/.X11-unix
USER bot

COPY --chown=bot:bot entrypoint.sh ./
CMD ["./entrypoint.sh"]
