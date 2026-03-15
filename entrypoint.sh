#!/bin/sh
set -e

uv run alembic upgrade head

# Xvfb provides a virtual display for headed browser mode
# Cloudflare Turnstile requires headed mode to pass verification
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

exec uv run python -m bot
