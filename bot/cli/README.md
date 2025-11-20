# Claude Authorization Bot CLI

Command-line interface for managing Claude sessions and authorization codes using session paths.

## Overview

The CLI provides direct access to Playwright browser automation without requiring Telegram. Key features:

- **Direct session management** using file system paths
- **No Telegram required** for authorization code extraction
- **Batch operations** and scripting support
- **Health monitoring** of database and sessions

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

### Global Options

- `--log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]` - Set logging level

### Environment Variables

The CLI uses the same configuration as the bot. Set these variables:

```bash
export TELEGRAM_TOKEN=dummy  # Required by settings, not used by CLI
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/claude_bot  # Optional for list-chats
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

### `account` - Session Management

Group of commands for managing Claude sessions using file system paths.

#### `account init-session` - Initialize Session

Initialize a new Claude session at specified path.

```bash
python -m bot.cli account init-session SESSION_PATH EMAIL
```

**Arguments:**
- `SESSION_PATH` - Path where Playwright session will be stored (directory will be created)
- `EMAIL` - Email address for Claude account

**Example:**

```bash
# Initialize session in custom directory
python -m bot.cli account init-session /data/sessions/my-project user@example.com

# Initialize in current directory
python -m bot.cli account init-session ./my-session user@example.com
```

**Workflow:**

1. Creates session directory at specified path
2. Opens Claude login page in headless browser
3. Fills email and requests login link
4. Saves browser state to `SESSION_PATH/state.json`
5. Prompts you to check email for login link

**Output:**

```
🔄 Initializing session for user@example.com
📁 Session path: /data/sessions/my-project
✅ 📧 Email sent! Please check your inbox for the authorization link.

Next steps:
1. Check your email for the login link from Claude
2. Run: python -m bot.cli account process-login /data/sessions/my-project <login_url>
```

#### `account process-login` - Process Login Link

Complete authentication by processing the login link from email.

```bash
python -m bot.cli account process-login SESSION_PATH LOGIN_URL
```

**Arguments:**
- `SESSION_PATH` - Path to Playwright session directory (must exist from init-session)
- `LOGIN_URL` - Login URL from Claude email (e.g., `https://claude.ai/login?token=...`)

**Example:**

```bash
python -m bot.cli account process-login /data/sessions/my-project "https://claude.ai/login?token=abc123..."
```

**Output:**

```
🔄 Processing login link
📁 Session: /data/sessions/my-project
✅ Session authenticated successfully!

You can now use:
python -m bot.cli account get-code /data/sessions/my-project <auth_url>
```

#### `account get-code` - Extract Authorization Code

Extract authorization code from Claude authorization URL.

```bash
python -m bot.cli account get-code SESSION_PATH AUTH_URL
```

**Arguments:**
- `SESSION_PATH` - Path to authenticated Playwright session directory
- `AUTH_URL` - Authorization URL from Claude Code (e.g., `https://claude.ai/auth/authorize?...`)

**Example:**

```bash
python -m bot.cli account get-code /data/sessions/my-project "https://claude.ai/auth/authorize?client_id=..."
```

**Output:**

```
🔄 Extracting authorization code
📁 Session: /data/sessions/my-project

✅ Authorization code:

    ABC123XYZ456

Copy this code and paste it into Claude Code CLI.
```

#### `account list-chats` - List Chat Sessions

List all chat sessions from database with their session paths (bot-managed sessions only).

```bash
python -m bot.cli account list-chats [OPTIONS]
```

**Options:**
- `--format [table|json]` - Output format (default: table)

**Examples:**

```bash
# Table format (default)
python -m bot.cli account list-chats

# JSON format for scripting
python -m bot.cli account list-chats --format json
```

**Table Output:**

```
Chat ID         Thread     Email                          Session Path
------------------------------------------------------------------------------------------------------------------------
123456789       0          user1@example.com              /data/sessions/123456789
123456789       42         user2@example.com              /data/sessions/123456789/42
987654321       0          admin@example.com              /data/sessions/987654321

Total chats: 3

Use session paths with other commands:
  python -m bot.cli account get-code <session_path> <auth_url>
```

**JSON Output:**

```json
[
  {
    "chat_id": 123456789,
    "thread_id": 0,
    "email": "user1@example.com",
    "session_path": "/data/sessions/123456789",
    "created_at": "2025-11-20T10:30:00",
    "last_used": "2025-11-20T15:45:00"
  },
  ...
]
```

**Note:** This command requires database access and only shows sessions created by the Telegram bot. For manually created sessions (via `init-session`), simply use the session path directly.

#### `account delete-session` - Delete Session

Delete a Claude session directory and all its contents.

```bash
python -m bot.cli account delete-session SESSION_PATH [OPTIONS]
```

**Arguments:**
- `SESSION_PATH` - Path to Playwright session directory to delete

**Options:**
- `--force` - Skip confirmation prompt

**Example:**

```bash
# Delete with confirmation
python -m bot.cli account delete-session /data/sessions/my-project

# Delete without confirmation
python -m bot.cli account delete-session /data/sessions/my-project --force
```

**Output:**

```
Delete session at /data/sessions/my-project? [y/N]: y
✅ Deleted session: /data/sessions/my-project
```

## Complete Workflow

### 1. Initialize New Session

```bash
# Step 1: Create session
python -m bot.cli account init-session ./my-claude-session myemail@example.com

# Step 2: Check email and copy login link

# Step 3: Process login link
python -m bot.cli account process-login ./my-claude-session "https://claude.ai/login?token=..."
```

### 2. Get Authorization Code

```bash
# When Claude Code prompts for authorization
python -m bot.cli account get-code ./my-claude-session "https://claude.ai/auth/authorize?..."
```

### 3. List Bot-Managed Sessions

```bash
# See all sessions created by Telegram bot
python -m bot.cli account list-chats

# Get specific session path
python -m bot.cli account list-chats --format json | jq '.[] | select(.email=="user@example.com") | .session_path'
```

## Use Cases

### CLI-Only Workflow (No Telegram Bot)

Create and manage sessions entirely from command line:

```bash
# Initialize session
python -m bot.cli account init-session ~/claude-sessions/work work@company.com

# Process login (after receiving email)
python -m bot.cli account process-login ~/claude-sessions/work "https://claude.ai/login?token=..."

# Get codes as needed
python -m bot.cli account get-code ~/claude-sessions/work "https://claude.ai/auth/authorize?..."
```

### Using Bot-Created Sessions

If you have sessions created by the Telegram bot, find their paths:

```bash
# Find path for specific chat
SESSION_PATH=$(python -m bot.cli account list-chats --format json | jq -r '.[] | select(.chat_id==123456789) | .session_path')

# Use the session
python -m bot.cli account get-code "$SESSION_PATH" "https://claude.ai/auth/authorize?..."
```

### Batch Code Extraction

Extract codes for multiple authorization URLs:

```bash
#!/bin/bash
SESSION_PATH="/data/sessions/my-project"

# Read URLs from file
while IFS= read -r auth_url; do
  echo "Processing: $auth_url"
  python -m bot.cli account get-code "$SESSION_PATH" "$auth_url"
done < auth_urls.txt
```

### Session Maintenance

```bash
# Check system health
python -m bot.cli health

# List all bot-managed sessions
python -m bot.cli account list-chats

# Clean up old session
python -m bot.cli account delete-session /data/sessions/old-project --force
```

## Session Directory Structure

Each session is stored in a directory with this structure:

```
/path/to/session/
├── state.json           # Playwright browser state (cookies, storage)
├── error_init.png       # Screenshot if initialization fails (optional)
├── error_login.png      # Screenshot if login fails (optional)
└── error_extract.png    # Screenshot if extraction fails (optional)
```

**Important:**
- Session directories are created with `0o700` permissions (owner only)
- `state.json` contains authentication cookies - keep it secure
- Error screenshots are saved automatically for debugging

## Architecture

### Session Path vs Chat ID

The CLI uses **session paths** instead of Telegram-specific `chat_id` and `thread_id`:

- **More flexible**: Create sessions anywhere on the filesystem
- **More portable**: No dependency on Telegram database
- **More explicit**: Session location is clear from the path
- **Bot compatible**: Can use sessions created by Telegram bot via `list-chats`

### Services Used

The CLI uses the same underlying services as the Telegram bot:

- **PlaywrightService** - Browser automation (init, login, code extraction)
- **ChatSessionRepository** - Database access (only for `list-chats` command)
- **Settings** - Configuration from environment/`.env`

All browser operations go through PlaywrightService, ensuring consistency between bot and CLI.

## Troubleshooting

### "TELEGRAM_TOKEN is required"

The Settings class requires `TELEGRAM_TOKEN` even for CLI. Set a dummy value:

```bash
export TELEGRAM_TOKEN=cli_dummy_token
```

Or in `.env`:

```
TELEGRAM_TOKEN=cli_dummy_token
```

### "Database connection failed" (for list-chats)

The `list-chats` command requires database access. Ensure PostgreSQL is running and set:

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/claude_bot
```

Other commands (`init-session`, `get-code`, etc.) **do not** require database access.

### "Session not found"

Make sure you've run `init-session` and `process-login` before `get-code`:

```bash
# Must run in order:
python -m bot.cli account init-session ./session email@example.com
python -m bot.cli account process-login ./session <login_url>
python -m bot.cli account get-code ./session <auth_url>  # Now works
```

### "Session expired or invalid"

If a session expires, simply re-initialize:

```bash
python -m bot.cli account delete-session ./session --force
python -m bot.cli account init-session ./session email@example.com
# ... repeat login process
```

### Debug Mode

Enable debug logging to see detailed information:

```bash
python -m bot.cli --log-level DEBUG account get-code ./session <auth_url>
```

## Comparison with Telegram Bot

| Feature | CLI | Telegram Bot |
|---------|-----|--------------|
| Session creation | `init-session <path>` | `/init_session` in chat |
| Session storage | Custom path | `chat_id/thread_id` based |
| Code extraction | Direct command | `/get_code` in chat |
| Database required | No (except list-chats) | Yes (all operations) |
| Multi-user | No (single operator) | Yes (per chat/topic) |
| Authorization | File-based | Chat-based permissions |

Use **CLI** for:
- Personal development workflow
- Automation and scripting
- Direct control over session location
- No Telegram access scenarios

Use **Telegram Bot** for:
- Team collaboration
- Chat-based workflows
- Multiple independent sessions (per topic)
- Permission management (admins only)
