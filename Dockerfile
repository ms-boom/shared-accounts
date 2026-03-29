FROM python:3.12-slim

WORKDIR /app

# Install only what patchright install-deps won't cover
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    ca-certificates \
    fonts-liberation \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer — rebuilds only when lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Install Patchright browser + system deps, clean all caches in one layer
RUN .venv/bin/patchright install chrome && \
    .venv/bin/patchright install-deps && \
    rm -rf /root/.cache /tmp/* /var/lib/apt/lists/*

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
