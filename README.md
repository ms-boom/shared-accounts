# Telegram Bot Template

Production-ready Telegram bot template with group management, built with aiogram 3.x, SQLAlchemy, and modern Python practices.

## Features

- **Group Management**: Automatic group registration, permission checking with caching
- **Clean Architecture**: Separation of concerns with services, repositories, and handlers
- **Dependency Injection**: Using punq for clean dependency management
- **Database Support**: SQLAlchemy 2.0 with async support, Alembic migrations
- **FSM States**: Built-in FSM for complex dialogues
- **Type Safety**: Full type hints with mypy strict mode
- **Code Quality**: Configured ruff linter, pre-commit hooks
- **Modern Python**: Python 3.12+, async/await throughout

## Quick Start

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- [Task](https://taskfile.dev/) for running commands (optional but recommended)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)

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
   # Edit .env and add your TELEGRAM_TOKEN
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

6. **Run the bot**
   ```bash
   task run
   ```

   Or manually:
   ```bash
   python -m bot
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
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── database.py        # Database connection
│   │   └── repositories/      # Repository pattern
│   ├── services/               # Business logic
│   │   ├── group_service.py
│   │   ├── permission_service.py
│   │   └── user_service.py
│   ├── filters/                # Aiogram filters
│   ├── middleware/             # Middleware
│   ├── handlers/               # Message handlers
│   ├── states/                 # FSM states
│   └── __main__.py            # Entry point
├── migrations/                 # Alembic migrations
├── tests/                      # Tests
├── .env.example               # Environment template
├── pyproject.toml             # Project config
├── Taskfile.yaml              # Task runner config
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
ruff check --fix bot tests     # Format code
mypy bot                        # Type check
pytest                          # Run tests
```

## Configuration

All configuration is done via environment variables in `.env`:

```env
# Required
TELEGRAM_TOKEN=your_bot_token_here

# Optional
DATABASE_URL=sqlite+aiosqlite:///./bot.db
LOG_LEVEL=INFO
DEBUG=False
FSM_STORAGE_TYPE=memory
PERMISSION_CACHE_TTL=300
```

## Architecture Patterns

### Repository Pattern
All database operations go through repositories for clean separation:

```python
group_repository = GroupRepository(database)
group = await group_repository.get_by_id(chat_id)
```

### Service Layer
Business logic is encapsulated in services:

```python
group_service = GroupService(database)
await group_service.register_group(chat)
```

### Permission Checking
Built-in permission service with caching:

```python
@router.message(Command("admin"), IsGroupAdmin())
async def admin_handler(message: Message):
    # Only admins can reach here
    pass
```

### Automatic Group Registration
Groups are automatically registered when bot interacts with them via middleware.

## Adding Your Own Features

### 1. Create a New Handler

```python
# bot/handlers/my_feature.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="my_feature")

@router.message(Command("mycommand"))
async def my_command_handler(message: Message):
    await message.reply("Hello from my feature!")
```

### 2. Register the Router

```python
# bot/__main__.py
from bot.handlers import my_feature

# ...
dp.include_router(my_feature.router)
```

### 3. Create Database Models (if needed)

```python
# bot/db/models.py
class MyModel(Base):
    __tablename__ = "my_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    # ... your fields
```

### 4. Create Migration

```bash
task db:revision -- -m "add my_table"
task db:upgrade
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

1. **Use PostgreSQL** instead of SQLite:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
   ```

2. **Use Redis for FSM**:
   ```env
   FSM_STORAGE_TYPE=redis
   REDIS_URL=redis://localhost:6379/0
   ```

3. **Set production settings**:
   ```env
   DEBUG=False
   LOG_LEVEL=WARNING
   ```

4. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Use process manager** (systemd, supervisor, docker):
   ```bash
   python -m bot
   ```

## Code Quality Tools

- **ruff**: Linting and formatting (replaces black, isort, flake8)
- **mypy**: Static type checking
- **prek**: Pre-commit hooks management
- **pytest**: Testing framework

## Principles

This template follows "Functional Clarity" principles:

- **Limited Responsibility**: Each module does one thing
- **Explicit Errors**: Fail-fast with clear error messages
- **Minimal Dependencies**: Only essential external packages
- **Type Safety**: Full type hints throughout
- **Testability**: Easy to test with mocked dependencies

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
