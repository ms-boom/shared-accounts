# Claude Authorization Bot CLI

Command-line interface for managing Claude sessions and authorization codes.

## Overview

The CLI provides direct access to the same Playwright services and database that the Telegram bot uses. This allows for:

- Managing sessions outside of Telegram
- Batch operations on sessions
- Debugging and health checks
- Integration with scripts and automation

## Installation

The CLI is automatically available after installing the project:

```bash
uv sync
source .venv/bin/activate
```

## Usage

Run the CLI using:

```bash
python -m bot.cli [OPTIONS] COMMAND [ARGS]...
```

Or if the package is installed (with `tool.uv.package = true`):

```bash
claude-bot [OPTIONS] COMMAND [ARGS]...
```

### Global Options

- `--log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]` - Set logging level

### Environment Variables

The CLI uses the same configuration as the bot. Make sure to set:

```bash
export TELEGRAM_TOKEN=your_token  # Required by settings, but not used in CLI
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/claude_bot
```

Or create a `.env` file in the project root.

## Commands

### `health` - System Health Check

Check the status of database, sessions, and tasks.

```bash
python -m bot.cli health [OPTIONS]
```

**Options:**
- `--format [text|json]` - Output format (default: text)

**Example:**

```bash
# Text format (default)
python -m bot.cli health

# JSON format for scripting
python -m bot.cli health --format json
```

**Output:**

```
✅ System Health Status

==================================================

✅ Database: CONNECTED
✅ Active sessions: 3
✅ Pending tasks: 0

==================================================

✅ All systems operational
```

### `account` - Account Management

Group of commands for managing Claude sessions.

#### `account init-session` - Initialize Session

Initialize a new Claude session for a chat.

```bash
python -m bot.cli account init-session CHAT_ID [THREAD_ID] EMAIL
```

**Arguments:**
- `CHAT_ID` - Telegram chat ID (integer)
- `THREAD_ID` - Telegram thread ID (default: 0 for main chat)
- `EMAIL` - Email address for Claude account

**Example:**

```bash
# Initialize session for main chat
python -m bot.cli account init-session 123456789 0 user@example.com

# Initialize session for topic in supergroup
python -m bot.cli account init-session 123456789 42 user@example.com
```

**Workflow:**

1. Opens Claude login page
2. Fills email and requests login link
3. Saves session to database
4. Prompts you to check email and use `process-login` command

#### `account process-login` - Process Login Link

Complete authentication by processing the login link from email.

```bash
python -m bot.cli account process-login CHAT_ID [THREAD_ID] LOGIN_URL
```

**Arguments:**
- `CHAT_ID` - Telegram chat ID
- `THREAD_ID` - Telegram thread ID (default: 0)
- `LOGIN_URL` - Login URL from Claude email

**Example:**

```bash
python -m bot.cli account process-login 123456789 0 "https://claude.ai/login?token=..."
```

#### `account get-code` - Extract Authorization Code

Extract authorization code from Claude authorization URL.

```bash
python -m bot.cli account get-code CHAT_ID [THREAD_ID] AUTH_URL
```

**Arguments:**
- `CHAT_ID` - Telegram chat ID
- `THREAD_ID` - Telegram thread ID (default: 0)
- `AUTH_URL` - Authorization URL from Claude Code

**Example:**

```bash
python -m bot.cli account get-code 123456789 0 "https://claude.ai/auth/authorize?..."
```

**Output:**

```
✅ Authorization code:

    ABC123XYZ456

Copy this code and paste it into Claude Code CLI.
```

#### `account list-sessions` - List Sessions

List all active Claude sessions.

```bash
python -m bot.cli account list-sessions [OPTIONS]
```

**Options:**
- `--chat-id INTEGER` - Filter by specific chat ID
- `--format [table|json]` - Output format (default: table)

**Examples:**

```bash
# List all sessions (table format)
python -m bot.cli account list-sessions

# List sessions for specific chat
python -m bot.cli account list-sessions --chat-id 123456789

# JSON format for scripting
python -m bot.cli account list-sessions --format json
```

**Table Output:**

```
Chat ID         Thread     Email                          Created              Last Used
----------------------------------------------------------------------------------------------------
123456789       0          user1@example.com              2025-11-20 10:30     2025-11-20 15:45
123456789       42         user2@example.com              2025-11-19 14:20     Never
987654321       0          admin@example.com              2025-11-18 09:15     2025-11-20 12:30

Total sessions: 3
```

#### `account delete-session` - Delete Session

Delete a Claude session for a chat.

```bash
python -m bot.cli account delete-session CHAT_ID [THREAD_ID] [OPTIONS]
```

**Arguments:**
- `CHAT_ID` - Telegram chat ID
- `THREAD_ID` - Telegram thread ID (default: 0)

**Options:**
- `--force` - Skip confirmation prompt

**Example:**

```bash
# Delete session with confirmation
python -m bot.cli account delete-session 123456789 0

# Delete without confirmation
python -m bot.cli account delete-session 123456789 0 --force
```

## Common Use Cases

### Check System Health

```bash
python -m bot.cli health
```

### Initialize New Session

```bash
# Step 1: Initialize session
python -m bot.cli account init-session 123456789 0 user@example.com

# Step 2: Check email and copy login link, then:
python -m bot.cli account process-login 123456789 0 "https://claude.ai/login?token=..."

# Step 3: Get authorization code when needed
python -m bot.cli account get-code 123456789 0 "https://claude.ai/auth/authorize?..."
```

### List All Sessions

```bash
python -m bot.cli account list-sessions
```

### Export Sessions to JSON

```bash
python -m bot.cli account list-sessions --format json > sessions.json
```

### Delete Old Sessions

```bash
# List sessions first
python -m bot.cli account list-sessions

# Delete specific session
python -m bot.cli account delete-session 123456789 0 --force
```

## Integration with Scripts

The CLI is designed to work well in scripts and automation:

```bash
#!/bin/bash

# Check health
if ! python -m bot.cli health --format json | jq -e '.status == "healthy"' > /dev/null; then
  echo "System unhealthy!"
  exit 1
fi

# List sessions
python -m bot.cli account list-sessions --format json | jq '.[] | select(.last_used == null)'

# Get code for automated workflows
CODE=$(python -m bot.cli account get-code 123456789 0 "$AUTH_URL" | grep -oP '(?<=    ).*')
echo "Code: $CODE"
```

## Architecture

The CLI uses the same services as the Telegram bot:

- **PlaywrightService** - Browser automation for Claude interactions
- **ChatSessionRepository** - Database operations for sessions
- **TaskRepository** - Task queue management
- **Settings** - Application configuration

All operations use the same:
- Database connections
- Playwright sessions (stored in `SESSION_DIR`)
- Configuration (from `.env` or environment variables)

This ensures consistency between bot and CLI operations.

## Troubleshooting

### "TELEGRAM_TOKEN is required"

Even though the CLI doesn't use the Telegram bot, the Settings class requires it. Set a dummy value:

```bash
export TELEGRAM_TOKEN=dummy_token_for_cli
```

### "Database connection failed"

Make sure PostgreSQL is running and `DATABASE_URL` is set correctly:

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/claude_bot
```

### "Session not found"

The session must be initialized first with `account init-session` and completed with `account process-login`.

### Debug Mode

Enable debug logging to see detailed information:

```bash
python -m bot.cli --log-level DEBUG health
```

## Development

The CLI is located in `bot/cli/`:

```
bot/cli/
├── __init__.py           # Package marker
├── __main__.py          # CLI entry point
└── commands/            # Command modules
    ├── account.py       # Account management commands
    └── health.py        # Health check command
```

Adding new commands:

1. Create a new file in `bot/cli/commands/`
2. Define Click commands or groups
3. Import and register in `bot/cli/__main__.py`
