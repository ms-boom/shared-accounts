#!/bin/sh
set -e

# Named Docker volumes are created by the daemon as root:root.
# Fix ownership before any application code runs.
chown -R bot:bot /data

uv run alembic upgrade head

# Xvfb provides a virtual display for headed browser mode.
# Cloudflare Turnstile requires headed mode to pass verification.
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

exec uv run python -m bot
