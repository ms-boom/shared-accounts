# Claude Authorization Bot

Telegram bot для автоматизации получения авторизационных кодов Claude Code через headless браузер (Playwright).

## Features

- **Claude Authentication Automation**: Автоматическая инициализация сессий и извлечение auth кодов
- **Telegram Topics Support**: Независимые сессии для каждого топика в супергруппе (thread_id)
- **Headless Browser**: Playwright для автоматизации взаимодействия с Claude.ai
- **Task Queue**: PostgreSQL-based очередь задач с поддержкой параллельной обработки (FOR UPDATE SKIP LOCKED)
- **Group Management**: Контроль доступа (только админы инициализируют сессии)
- **Clean Architecture**: Разделение на handlers, services, repositories, worker
- **Session Isolation**: Изолированные браузерные сессии для каждого чата/топика
- **Type Safety**: Полная типизация с mypy, современный Python 3.12+
- **Code Quality**: ruff linter, pre-commit hooks, pytest

## Quick Start

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- [Task](https://taskfile.dev/) for running commands (optional but recommended)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- PostgreSQL 15+ database
- Docker & Docker Compose (for production deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd shared-accounts
   ```

2. **Install dependencies**
   ```bash
   uv sync --group dev
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add:
   # - TELEGRAM_TOKEN (from @BotFather)
   # - DATABASE_URL (PostgreSQL connection string)
   ```

4. **Run database migrations**
   ```bash
   task db:upgrade
   ```

   Or manually:
   ```bash
   alembic upgrade head
   ```

5. **Install pre-commit hooks (optional)**
   ```bash
   task prek:install
   ```

6. **Run the bot and worker**

   Using Docker Compose (recommended):
   ```bash
   docker-compose up
   ```

   Or manually (requires two terminals):
   ```bash
   # Terminal 1: Bot service
   python -m bot

   # Terminal 2: Worker service
   python -m bot.worker
   ```

## Project Structure

```
.
├── bot/                        # Main bot package
│   ├── core/                   # Core components
│   │   ├── config.py          # Pydantic settings
│   │   ├── container.py       # DI container
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── logging_config.py  # Logging setup
│   ├── db/                     # Database layer
│   │   ├── models.py          # SQLAlchemy models (ChatSession, Task)
│   │   ├── database.py        # Database connection
│   │   └── repositories/      # Repository pattern
│   │       ├── chat_session_repository.py
│   │       ├── task_repository.py
│   │       └── ...
│   ├── services/               # Business logic
│   │   ├── permission_service.py
│   │   └── user_service.py
│   ├── worker/                 # Background task processing
│   │   ├── task_worker.py     # Main worker loop
│   │   ├── playwright_service.py  # Playwright automation
│   │   └── __main__.py        # Worker entry point
│   ├── handlers/               # Message handlers
│   │   ├── claude_auth.py     # /init_session, /get_code, /health
│   │   └── ...
│   ├── middleware/             # Middleware
│   ├── filters/                # Aiogram filters
│   └── __main__.py            # Bot entry point
├── migrations/                 # Alembic migrations
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_topic_support.py
├── features/                   # Feature documentation
├── tests/                      # Tests
├── docker-compose.yml         # Docker services config
├── Dockerfile                 # Bot service image
├── Dockerfile.worker          # Worker service image
├── .env.example               # Environment template
├── pyproject.toml             # Project config
├── Taskfile.yaml              # Task runner config
├── CLAUDE.md                  # Full project documentation
└── README.md                  # This file
```

## Available Commands

If you have [Task](https://taskfile.dev/) installed:

### Development
- `task install` - Install dependencies
- `task run` - Run the bot
- `task format` - Format code with ruff
- `task lint` - Run all linters
- `task test` - Run tests
- `task clean` - Clean up cache files

### Code Quality
- `task format` - Auto-format code
- `task lint:ruff` - Check code with ruff
- `task lint:mypy` - Type check with mypy
- `task prek:install` - Install pre-commit hooks
- `task prek` - Run pre-commit manually

### Database
- `task db:upgrade` - Apply migrations
- `task db:downgrade` - Rollback one migration
- `task db:revision -- -m "message"` - Create new migration
- `task db:current` - Show current migration

### Testing
- `task test` - Run all tests
- `task test:unit` - Run unit tests only
- `task coverage` - Run tests with coverage

Without Task, use the commands directly:
```bash
uv sync --group dev            # Install dependencies
python -m bot                   # Run bot
python -m bot.worker            # Run worker
ruff check --fix bot tests     # Format code
mypy bot                        # Type check
pytest                          # Run tests
```

## Bot Usage

Once the bot is running, use these commands in Telegram:

- `/init_session <email>` - Initialize Claude session (admin only in groups)
- `/get_code <auth_url>` - Extract authorization code from Claude URL
- `/health` - Check bot status and active sessions

**Topics Support**: All commands work in both main chat and topics. Each topic gets an independent session isolated from others.

## Configuration

All configuration is done via environment variables in `.env`:

```env
# Required
TELEGRAM_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://user:pass@postgres/claude_bot

# Optional
LOG_LEVEL=INFO
DEBUG=False
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT=30000
WORKER_POLL_INTERVAL=2
SESSION_DIR=/data/sessions
ERROR_DIR=/data/errors
```

## Architecture Patterns

### Worker Pattern + Task Queue
The bot uses a PostgreSQL-based task queue with worker processes:

```
Bot (aiogram) → Tasks Table → Worker (Playwright)
```

Tasks are processed with `SELECT FOR UPDATE SKIP LOCKED` for concurrent safety.

### Repository Pattern
All database operations go through repositories:

```python
session_repo = ChatSessionRepository(database)
session = await session_repo.get_by_chat_id(chat_id, thread_id)
```

### Session Isolation
Each (chat_id, thread_id) pair gets an isolated Playwright browser context:

```
/data/sessions/
├── {chat_id}/              # Main chat sessions
│   └── state.json
└── {chat_id}/{thread_id}/  # Topic sessions
    └── state.json
```

### Topics Support
All handlers extract thread_id automatically:

```python
def get_thread_id(message: Message) -> int:
    return message.message_thread_id if message.message_thread_id else 0
```

thread_id = 0 means main chat, >0 means topic.

## How It Works

### User Journey

1. **Initialize Session**
   - User: `/init_session user@example.com` (in chat or topic)
   - Bot: Creates task, worker opens claude.ai, fills email
   - Worker: Sends "Check your email" screenshot
   - User receives: "Email sent! Please send the authorization link"

2. **Process Login Link**
   - User: Forwards Claude login link from email
   - Bot: Detects URL, creates process_login_link task
   - Worker: Opens link, waits for authentication
   - User receives: "Session initialized successfully!"

3. **Extract Authorization Code**
   - User: `/get_code https://claude.ai/auth/authorize?...`
   - Bot: Creates get_code task
   - Worker: Opens URL, extracts code from page
   - User receives: "Authorization code: ABC123XYZ"

### Adding New Task Types

1. Define task processor in `bot/worker/task_worker.py`:
   ```python
   async def process_my_task(self, task_id, chat_id, thread_id, payload):
       # Your logic here
       result = await self.playwright.do_something(...)
       await self.task_repo.update_status(task_id, "done", result)
       await self.send_message(chat_id, result, thread_id)
   ```

2. Add handler in `bot/handlers/`:
   ```python
   await task_repo.create(
       chat_id=message.chat.id,
       user_id=message.from_user.id,
       task_type="my_task",
       payload={"key": "value"},
       thread_id=get_thread_id(message)
   )
   ```

## Development Workflow

1. **Make changes** to your code
2. **Format code**: `task format`
3. **Check quality**: `task lint`
4. **Run tests**: `task test`
5. **Commit**: Git hooks will run automatically if installed

## Testing

```bash
# Run all tests
task test

# Run with coverage
task coverage

# Run specific tests
pytest tests/unit/test_services.py
```

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your TELEGRAM_TOKEN and other settings

# 2. Start all services
docker-compose up -d

# 3. Check logs
docker-compose logs -f bot
docker-compose logs -f worker

# 4. Stop services
docker-compose down
```

Services:
- `postgres` - PostgreSQL database
- `bot` - Telegram bot service (aiogram)
- `worker` - Task worker service (Playwright)

### Manual Deployment

1. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

2. **Set production settings**:
   ```env
   DEBUG=False
   LOG_LEVEL=WARNING
   PLAYWRIGHT_HEADLESS=true
   ```

3. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start services** (use systemd or supervisor):
   ```bash
   # Service 1: Bot
   python -m bot

   # Service 2: Worker (can run multiple instances)
   python -m bot.worker
   ```

### Scaling

Run multiple worker instances for better throughput:
```bash
docker-compose up -d --scale worker=3
```

Workers use PostgreSQL locking (`FOR UPDATE SKIP LOCKED`), so multiple instances can safely process tasks concurrently.

## Code Quality Tools

- **ruff**: Linting and formatting (replaces black, isort, flake8)
- **mypy**: Static type checking
- **prek**: Pre-commit hooks management
- **pytest**: Testing framework

## Principles

This project follows "Functional Clarity" principles:

- **Limited Responsibility**: Each function/module does one thing (functions 20-30 lines max)
- **Explicit Errors**: Fail-fast with custom exception classes and clear error messages
- **Minimal Dependencies**: Standard library first, external packages only when necessary
- **Type Safety**: Full type hints with mypy strict mode
- **Testability**: Pure functions, explicit inputs/outputs, isolated side effects
- **Modern Python**: 3.12+, async/await, pathlib, context managers

See [CLAUDE.md](CLAUDE.md) for full project documentation including:
- Complete architecture overview
- Feature design documents (features/ directory)
- Development practices and style guide
- Database schema and migration strategy

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `task qa` to ensure quality
5. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.
