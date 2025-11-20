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

## User Journey

### 1. Инициализация сессии (первый раз для группы/чата)

**Администратор группы:**

1. Добавьте бота в вашу Telegram группу
2. Выполните команду:
   ```
   /init_session user@example.com
   ```

3. Бот ответит:
   ```
   🔄 Initializing session for user@example.com.
   Please wait for the authorization link request...
   ```

4. Через несколько секунд:
   ```
   📧 Email sent! Please send me the authorization link from your inbox.
   ```

5. **Откройте email** от Claude и скопируйте ссылку авторизации
6. **Отправьте ссылку боту** (просто вставьте URL в чат)
7. Бот автоматически определит ссылку и обработает её:
   ```
   🔄 Processing login link...
   ```

8. После успешной авторизации:
   ```
   ✅ Session initialized successfully!
   You can now use /get_code to extract authorization codes.
   ```

### 2. Получение авторизационного кода (регулярное использование)

**Любой участник группы:**

1. Скопируйте URL авторизации из Claude Code:
   ```
   https://claude.ai/auth/authorize?client_id=...&redirect_uri=...
   ```

2. Выполните команду:
   ```
   /get_code https://claude.ai/auth/authorize?client_id=...
   ```

3. Бот ответит:
   ```
   🔄 Extracting authorization code...
   ```

4. Через ~5-10 секунд вы получите код:
   ```
   ✅ Authorization code: `ABC123XYZ789`
   ```

5. Скопируйте код (одним кликом) и вставьте в Claude Code

### 3. Проверка статуса системы

```
/health
```

Ответ:
```
✅ Bot Status

• Database: ✅ Connected
• Active sessions: 3
• Pending tasks: 1
• Worker: Running
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

## CLI Usage

In addition to the Telegram bot, the project provides a command-line interface for direct session management.

### Quick Start

```bash
# Initialize new session
python -m bot.cli account init-session ./my-session user@example.com

# Process login link from email
python -m bot.cli account process-login ./my-session "https://claude.ai/login?token=..."

# Get authorization code
python -m bot.cli account get-code ./my-session "https://claude.ai/auth/authorize?..."

# List bot-managed sessions
python -m bot.cli account list-chats

# Check system health
python -m bot.cli health
```

### Key Features

- **Path-based sessions**: Create sessions anywhere on filesystem
- **No Telegram required**: Direct access to Playwright automation
- **Batch operations**: Script multiple authorization requests
- **Bot compatibility**: Can use sessions created by Telegram bot

### Available Commands

**account** - Session management:
- `init-session <path> <email>` - Initialize new session
- `process-login <path> <url>` - Complete authentication
- `get-code <path> <url>` - Extract authorization code
- `list-chats` - List bot-managed sessions
- `delete-session <path>` - Remove session

**health** - System monitoring:
- Check database connection
- Show active sessions count
- Display pending tasks

### Use Cases

**CLI-Only Workflow** (no Telegram):
```bash
# Create and manage sessions entirely from command line
python -m bot.cli account init-session ~/sessions/work work@company.com
python -m bot.cli account process-login ~/sessions/work <login_url>
python -m bot.cli account get-code ~/sessions/work <auth_url>
```

**Using Bot Sessions via CLI**:
```bash
# Find session path from bot
python -m bot.cli account list-chats

# Use bot's session
python -m bot.cli account get-code /data/sessions/123456789 <auth_url>
```

**Batch Processing**:
```bash
# Extract codes for multiple URLs
for url in $(cat urls.txt); do
  python -m bot.cli account get-code ./session "$url"
done
```

For complete CLI documentation, see [bot/cli/README.md](bot/cli/README.md).

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

## Architecture

### System Overview

```
┌─────────────────┐
│  Telegram API   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Bot Service   │ (aiogram)
│  - /init_session│
│  - /get_code    │
│  - /health      │
│  - Creates tasks│
└────────┬────────┘
         │
┌────────▼────────┐
│  PostgreSQL     │
│  - tasks queue  │
│  - chat_sessions│
│  (FOR UPDATE    │
│   SKIP LOCKED)  │
└────────┬────────┘
         │
┌────────▼────────┐
│ Worker Service  │ (1+ instances)
│  - Dequeue tasks│
│  - Playwright   │
│  - Extract code │
│  - Send results │
└────────┬────────┘
         │
┌────────▼────────┐
│  File System    │
│  /data/sessions/{chat_id}/
│  /data/logs/bot.log
│  /data/errors/{task_id}.png
└─────────────────┘
```

### Architecture Patterns

#### Worker Pattern + Task Queue
The bot uses a PostgreSQL-based task queue with worker processes:

```
Bot (aiogram) → Tasks Table → Worker (Playwright)
```

Tasks are processed with `SELECT FOR UPDATE SKIP LOCKED` for concurrent safety.

#### Repository Pattern
All database operations go through repositories:

```python
session_repo = ChatSessionRepository(database)
session = await session_repo.get_by_chat_id(chat_id, thread_id)
```

#### Session Isolation
Each (chat_id, thread_id) pair gets an isolated Playwright browser context:

```
/data/sessions/
├── {chat_id}/              # Main chat sessions
│   └── state.json
└── {chat_id}/{thread_id}/  # Topic sessions
    └── state.json
```

#### Topics Support
All handlers extract thread_id automatically:

```python
def get_thread_id(message: Message) -> int:
    return message.message_thread_id if message.message_thread_id else 0
```

thread_id = 0 means main chat, >0 means topic.

## Database Schema

### Tables

**`chat_sessions`** - хранит Playwright сессии для каждого чата
- `chat_id` (PK) - Telegram chat_id
- `thread_id` (PK) - Telegram message_thread_id (0 = main chat)
- `email` - email адрес Claude аккаунта
- `session_path` - путь к данным сессии Playwright
- `created_at` - когда сессия создана
- `last_used` - последнее использование

**`tasks`** - очередь фоновых задач
- `id` (UUID PK) - уникальный ID задачи
- `chat_id` - Telegram chat_id
- `thread_id` - Telegram message_thread_id
- `user_id` - Telegram user_id инициатора
- `task_type` - тип задачи: `init_session`, `process_login_link`, `get_code`
- `payload` (JSONB) - данные задачи
- `status` - статус: `pending`, `processing`, `done`, `failed`
- `result` - результат или сообщение об ошибке
- `created_at`, `updated_at`

### Migrations

```bash
# Apply migrations
task db:upgrade
# or: alembic upgrade head

# Create new migration
task db:revision -- -m "description"
# or: alembic revision --autogenerate -m "description"

# Rollback migration
task db:downgrade
# or: alembic downgrade -1

# Show current version
task db:current
# or: alembic current
```

## How It Works

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

### Local Development Without Docker

1. **Install dependencies**
   ```bash
   uv sync --group dev
   ```

2. **Install Playwright browsers**
   ```bash
   uv run playwright install chromium
   ```

3. **Start PostgreSQL**
   ```bash
   docker run -d \
     -p 5432:5432 \
     -e POSTGRES_DB=claude_bot \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=postgres \
     postgres:15-alpine
   ```

4. **Apply migrations**
   ```bash
   uv run alembic upgrade head
   ```

5. **Run bot and worker in separate terminals**
   ```bash
   # Terminal 1: Bot
   uv run python -m bot

   # Terminal 2: Worker
   uv run python -m bot.worker
   ```

### Code Quality Workflow

1. **Make changes** to your code
2. **Format code**: `task format`
3. **Check quality**: `task lint`
4. **Run tests**: `task test`
5. **Commit**: Git hooks will run automatically if installed

```bash
# Format code
task format
# or: uv run ruff format bot tests

# Check linting
task lint:ruff
# or: uv run ruff check --fix bot tests

# Type checking
task lint:mypy
# or: uv run mypy bot

# Run all linters
task lint

# Run tests
task test
# or: uv run pytest

# Run tests with coverage
task coverage
# or: uv run pytest --cov=bot
```

## Testing

```bash
# Run all tests
task test

# Run with coverage
task coverage

# Run specific tests
pytest tests/unit/test_services.py

# Run only unit tests
task test:unit
```

## Troubleshooting

### Бот не отвечает

1. Проверьте логи:
   ```bash
   docker-compose logs -f bot worker
   ```

2. Проверьте статус сервисов:
   ```bash
   docker-compose ps
   ```

3. Проверьте подключение к БД:
   ```bash
   docker-compose exec postgres psql -U postgres -d claude_bot -c "SELECT 1"
   ```

### Worker не обрабатывает задачи

1. Проверьте что Playwright установлен:
   ```bash
   docker-compose exec worker playwright --version
   ```

2. Проверьте очередь задач:
   ```bash
   docker-compose exec postgres psql -U postgres -d claude_bot -c \
     "SELECT id, task_type, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 10"
   ```

3. Перезапустите worker:
   ```bash
   docker-compose restart worker
   ```

### Сессия устарела / невалидна

Если получаете ошибку "Session expired or invalid":

1. Удалите старую сессию:
   ```bash
   docker-compose exec postgres psql -U postgres -d claude_bot -c \
     "DELETE FROM chat_sessions WHERE chat_id = YOUR_CHAT_ID"
   ```

2. Переинициализируйте сессию:
   ```
   /init_session user@example.com
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

### Production Best Practices

1. **Используйте внешний PostgreSQL**:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@prod-db-host:5432/claude_bot
   ```

2. **Настройте логирование**:
   ```env
   LOG_LEVEL=WARNING
   LOG_DIR=/var/log/claude-bot
   ```

3. **Используйте secrets manager** для TELEGRAM_TOKEN

4. **Настройте мониторинг** через `/health` endpoint

5. **Настройте backup БД** и volumes:
   ```bash
   docker volume ls
   docker run --rm -v shared-accounts_bot_data:/data -v $(pwd):/backup \
     ubuntu tar czf /backup/bot-data-$(date +%Y%m%d).tar.gz /data
   ```

6. **Масштабируйте workers** при необходимости:
   ```bash
   docker-compose up -d --scale worker=3
   ```

Workers use PostgreSQL locking (`FOR UPDATE SKIP LOCKED`), so multiple instances can safely process tasks concurrently.

## Code Quality Tools

- **ruff**: Linting and formatting (replaces black, isort, flake8)
- **mypy**: Static type checking
- **prek**: Pre-commit hooks management
- **pytest**: Testing framework

Configuration in `pyproject.toml`:
- `[tool.ruff]` - Ruff linter and formatter settings
- `[tool.mypy]` - Type checking configuration
- `[tool.pytest.ini_options]` - Test framework settings

## Principles

This project follows "Functional Clarity" principles:

- **Limited Responsibility**: Each function/module does one thing (functions 20-30 lines max)
- **Explicit Errors**: Fail-fast with custom exception classes and clear error messages
- **Minimal Dependencies**: Standard library first, external packages only when necessary
- **Type Safety**: Full type hints with mypy strict mode
- **Testability**: Pure functions, explicit inputs/outputs, isolated side effects
- **Modern Python**: 3.12+, async/await, pathlib, context managers
- **Domain-Oriented**: Code organized by functional areas, not technical layers
- **Explicit State Management**: Clear state transitions, context-dependent operations
- **Infrastructure Separation**: Business logic isolated from implementation details

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
