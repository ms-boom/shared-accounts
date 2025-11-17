# Claude Authorization Bot — Project Specification

## Overview
Claude Authorization Bot is a Telegram bot that simplifies obtaining authorization codes for Claude Code by automating the email-based login flow. The bot uses Playwright in headless mode to maintain authenticated sessions tied to Telegram chats, enabling users to quickly get authorization codes without manual browser interaction.

---

## Goals
- Provide a simple Telegram interface for Claude Code authorization
- Automate email-based login flow via Playwright
- Maintain persistent browser sessions per Telegram chat
- Process requests through a reliable queue system
- Ensure secure and isolated sessions

---

## Use Case Scenario

### Initial Setup (One-time per chat)
1. Admin adds bot to a Telegram group (or uses private chat)
2. Admin runs `/init_session email@example.com`
3. Bot:
   - Creates a new Playwright session tied to this chat_id
   - Opens `https://claude.ai/login`
   - Enters the provided email
   - Waits for authorization link
4. Admin receives authorization link via email
5. Admin sends link to bot
6. Bot:
   - Opens the link in its Playwright session
   - Completes authentication
   - Saves authenticated session to filesystem (keyed by chat_id)
   - Confirms success to admin

### Getting Authorization Codes (Regular usage)
1. User (in the same chat) runs `/get_code https://claude.ai/auth/...`
2. Bot:
   - Loads the saved Playwright session for this chat_id
   - Opens the provided URL
   - Extracts authorization code from the page
   - Sends code back to user

---

## Core Components

### 1. Telegram Bot (aiogram)
- Listens in group chats and private messages
- Commands:
  - `/init_session <email>` — Initialize new authenticated session for this chat
  - `/get_code <auth_url>` — Extract authorization code from URL
  - `/health` — Health check
- Uses PostgreSQL for task queueing
- Access control: Bot must be added by admin to group first

### 2. Task Queue (PostgreSQL)
- Manages pending authorization requests
- Uses `SELECT FOR UPDATE SKIP LOCKED` for reliable concurrent processing
- Tracks task status and metadata

### 3. Browser Automation (Playwright)
- Chrome/Chromium in **headless** mode
- Persistent browser contexts stored in filesystem
- Each chat_id has isolated browser profile at `/data/sessions/{chat_id}/`
- Session lifetime: persists until bot restart or explicit cleanup

### 4. Worker Service
- Processes tasks from PostgreSQL queue
- Handles Playwright automation:
  - Session initialization
  - Code extraction
- Error handling with retry logic
- Sends results back to Telegram

---

## Database Schema

### `chat_sessions`
| Column | Type | Notes |
|--------|------|-------|
| chat_id | bigint | Primary key, Telegram chat ID |
| email | text | Associated email address |
| session_path | text | Path to Playwright profile directory |
| created_at | timestamp | Session creation time |
| last_used | timestamp | Last successful code extraction |

### `tasks`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| chat_id | bigint | Telegram chat |
| user_id | bigint | Requesting user |
| task_type | text | init_session / get_code |
| payload | jsonb | Task-specific data (email, url, etc) |
| status | text | pending / processing / done / failed |
| result | text | Extracted code or error message |
| created_at | timestamp | |
| updated_at | timestamp | |

Queue processing query:
```sql
SELECT * FROM tasks
WHERE status = 'pending'
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

---

## Bot Command Flows

### `/init_session <email>`

**User Action:**
```
/init_session user@example.com
```

**Bot Flow:**
1. Validate email format
2. Check if session already exists for this chat_id
3. Create task in database:
   ```json
   {
     "task_type": "init_session",
     "chat_id": 12345,
     "payload": {"email": "user@example.com"}
   }
   ```
4. Reply: "🔄 Initializing session for user@example.com. Please wait for the authorization link request..."

**Worker Flow:**
1. Dequeue task
2. Create Playwright profile directory: `/data/sessions/{chat_id}/`
3. Launch browser with persistent context
4. Navigate to `https://claude.ai/login`
5. Find email input field (timeout: 30s)
6. Enter email
7. Click "Continue with email" button
8. Wait for "Check your email" confirmation page (timeout: 30s)
9. Update task status to `waiting_for_link`
10. Send to Telegram: "📧 Email sent! Please send me the authorization link from your inbox."

**User Provides Link:**
```
https://claude.ai/login?token=abc123...
```

**Bot Flow:**
1. Detect URL message in chat
2. Validate URL matches Claude login pattern
3. Update task with link:
   ```json
   {"payload": {"email": "...", "link": "https://..."}}
   ```

**Worker Flow:**
1. Navigate to provided link
2. Wait for successful authentication (timeout: 30s)
3. Verify session is authenticated (check for user profile element)
4. Save session to database:
   ```sql
   INSERT INTO chat_sessions (chat_id, email, session_path, created_at)
   VALUES (12345, 'user@example.com', '/data/sessions/12345', NOW());
   ```
5. Mark task as `done`
6. Send to Telegram: "✅ Session initialized successfully! You can now use `/get_code` to extract authorization codes."

---

### `/get_code <auth_url>`

**User Action:**
```
/get_code https://claude.ai/auth/authorize?client_id=...
```

**Bot Flow:**
1. Validate auth URL format
2. Check if session exists for this chat_id
   - If not: Reply "❌ No session found. Please run `/init_session <email>` first."
3. Create task:
   ```json
   {
     "task_type": "get_code",
     "chat_id": 12345,
     "payload": {"auth_url": "https://..."}
   }
   ```
4. Reply: "🔄 Extracting authorization code..."

**Worker Flow:**
1. Dequeue task
2. Load Playwright session from `/data/sessions/{chat_id}/`
3. Navigate to auth_url (timeout: 30s)
4. Wait for authorization code element (timeout: 30s)
   - Expected patterns:
     - `<code>` tag with text content
     - `<input>` with authorization code value
     - Specific CSS selector (to be determined from actual page structure)
5. Extract code text
6. Update task:
   ```sql
   UPDATE tasks
   SET status = 'done', result = '<extracted_code>'
   WHERE id = task_id;
   ```
7. Update last_used timestamp:
   ```sql
   UPDATE chat_sessions
   SET last_used = NOW()
   WHERE chat_id = 12345;
   ```
8. Send to Telegram: "✅ Authorization code: `<code>`"

---

## Error Handling

### Network Errors
- **Retry**: Up to 3 attempts with exponential backoff (2s, 4s, 8s)
- **Logging**: All network errors logged to file with full context
- **User Notification**: "⚠️ Network error. Retrying... (attempt X/3)"

### Invalid/Expired Links
- **Detection**: Page returns error or unexpected content
- **Response**: "❌ Authorization link is invalid or expired. Please run `/init_session <email>` again."
- **Action**: Mark task as failed, suggest restart

### Timeout Errors
- **Default timeout**: 30 seconds for all Playwright operations
- **Response**: "❌ Operation timed out. The page took too long to respond."
- **Logging**: Full stack trace + screenshot saved to `/data/errors/{task_id}.png`

### Session Not Found
- **Trigger**: `/get_code` called without initialized session
- **Response**: "❌ No active session found for this chat. Run `/init_session <email>` first."

### All Errors
- ✅ Notify user in chat with clear error message
- ✅ Log to file: `/data/logs/bot.log` with timestamp, task_id, stack trace
- ✅ Update task status to `failed` with error details in `result` field

---

## Security & Access Control

### Chat-Based Access
- Bot must be explicitly added to group by admin
- Once added, all group members can use bot commands
- Private chat: anyone who starts chat can use bot (optional: implement user whitelist)

### Session Isolation
- Each chat_id has completely isolated Playwright profile
- No cross-contamination between different chats/groups
- Profile directory permissions: `700` (owner-only)

### Data Storage
- Browser profiles: `/data/sessions/{chat_id}/`
- Logs: `/data/logs/bot.log`
- Error screenshots: `/data/errors/{task_id}.png`
- All sensitive data encrypted at rest (filesystem-level encryption recommended)

---

## Technical Stack

### Core Technologies
- **Python 3.11+**
- **aiogram 3.x** — Telegram Bot framework
- **Playwright** — Browser automation
- **PostgreSQL 15+** — Task queue and session storage
- **asyncio** — Async task processing

### Dependencies
```
aiogram>=3.0
playwright>=1.40
asyncpg>=0.29
pydantic>=2.0
structlog>=23.0
```

### Deployment Architecture
```
┌─────────────────┐
│  Telegram API   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Bot Service   │ (aiogram)
│  - Commands     │
│  - Task Create  │
└────────┬────────┘
         │
┌────────▼────────┐
│  PostgreSQL     │
│  - Tasks Queue  │
│  - Sessions     │
└────────┬────────┘
         │
┌────────▼────────┐
│ Worker Service  │
│  - Dequeue      │
│  - Playwright   │
│  - Extract Code │
└────────┬────────┘
         │
┌────────▼────────┐
│  File System    │
│  - /data/sessions/
│  - /data/logs/
└─────────────────┘
```

---

## Deployment

### Environment Variables
```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Database
DATABASE_URL=postgresql://user:pass@localhost/claude_bot

# Paths
DATA_DIR=/data
SESSION_DIR=/data/sessions
LOG_DIR=/data/logs

# Playwright
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT=30000

# Worker
WORKER_POLL_INTERVAL=1.0
WORKER_RETRY_ATTEMPTS=3
```

### Docker Compose (Recommended)
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: claude_bot
      POSTGRES_USER: claude_bot
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  bot:
    build: .
    command: python -m claude_bot.bot
    environment:
      TELEGRAM_BOT_TOKEN: ${BOT_TOKEN}
      DATABASE_URL: postgresql://claude_bot:${DB_PASSWORD}@postgres/claude_bot
    depends_on:
      - postgres
    volumes:
      - bot_data:/data

  worker:
    build: .
    command: python -m claude_bot.worker
    environment:
      DATABASE_URL: postgresql://claude_bot:${DB_PASSWORD}@postgres/claude_bot
      PLAYWRIGHT_HEADLESS: "true"
    depends_on:
      - postgres
    volumes:
      - bot_data:/data
    deploy:
      replicas: 2  # Can scale workers horizontally

volumes:
  postgres_data:
  bot_data:
```

---

## Logging & Monitoring

### Log Levels
- **DEBUG**: Playwright actions, page navigation
- **INFO**: Task lifecycle, user commands
- **WARNING**: Retries, timeouts
- **ERROR**: Failed tasks, exceptions

### Log Format (structlog)
```json
{
  "timestamp": "2025-01-17T10:30:45.123Z",
  "level": "info",
  "event": "task_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_id": 12345,
  "task_type": "get_code",
  "duration_ms": 2341
}
```

### Health Checks
- `/health` command returns:
  - Database connection status
  - Active sessions count
  - Pending tasks count
  - Worker status

---

## Future Enhancements

1. **Session Expiration**: Auto-detect expired sessions and notify users
2. **Session Health Check**: Periodic validation of stored sessions
3. **Multi-profile Support**: Allow multiple emails per chat
4. **Admin Commands**:
   - `/sessions` — List all active sessions
   - `/cleanup` — Remove old/unused sessions
5. **Metrics Dashboard**:
   - Request volume
   - Success/failure rates
   - Average response time
6. **Rate Limiting**: Prevent abuse from high-frequency requests
7. **Webhook Mode**: Replace polling with Telegram webhooks for better performance

---
