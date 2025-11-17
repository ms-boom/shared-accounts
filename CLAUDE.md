# Shared Accounts - Claude Authorization Bot

> **Telegram бот для автоматизации авторизации Claude Code через headless браузер**

---

## Описание проекта

**Claude Authorization Bot** — это Telegram-бот, который автоматизирует процесс получения авторизационных кодов для Claude Code. Вместо ручного открытия email, перехода по ссылкам и копирования кодов, пользователи получают их прямо в Telegram через простые команды.

### Ключевые возможности

- Автоматическая инициализация браузерных сессий для групп/чатов
- **Поддержка Telegram Topics** — независимые сессии для каждого топика в супергруппе
- Извлечение авторизационных кодов из Claude через headless браузер (Playwright)
- Групповое использование с контролем доступа (только админы инициализируют сессии)
- Очередь задач через PostgreSQL с поддержкой параллельной обработки
- Изолированные браузерные сессии для каждого чата и топика
- Автоматическая обработка ошибок и повторные попытки

---

## Структура проекта

```
.
├── bot/                           # Основной пакет бота
│   ├── core/                      # Ядро приложения
│   │   ├── config.py             # Конфигурация через Pydantic Settings
│   │   ├── container.py          # DI контейнер (punq)
│   │   ├── exceptions.py         # Кастомные исключения
│   │   └── logging_config.py     # Настройка структурированного логирования
│   ├── db/                        # Слой работы с БД
│   │   ├── database.py           # Подключение к БД (databases + asyncpg)
│   │   ├── models.py             # SQLAlchemy модели
│   │   ├── fsm_storage.py        # PostgreSQL FSM Storage для aiogram
│   │   └── repositories/         # Repository Pattern
│   │       ├── chat_session_repository.py
│   │       ├── group_repository.py
│   │       ├── task_repository.py
│   │       └── user_repository.py
│   ├── services/                  # Бизнес-логика (Service Layer)
│   │   ├── permission_service.py  # Проверка прав с кешированием
│   │   └── user_service.py
│   ├── handlers/                  # Telegram message handlers
│   │   ├── claude_auth.py        # Команды /init_session, /get_code, /health
│   │   ├── common.py
│   │   ├── group_admin.py
│   │   └── group_events.py
│   ├── middleware/                # Aiogram middleware
│   │   ├── error_handler.py      # Централизованная обработка ошибок
│   │   └── group_tracker.py      # Отслеживание групп
│   ├── filters/                   # Aiogram фильтры
│   │   ├── is_group_admin.py
│   │   ├── is_group.py
│   │   └── is_private_chat.py
│   ├── states/                    # FSM состояния
│   │   └── group_settings.py
│   ├── worker/                    # Worker service (обработка задач)
│   │   ├── __main__.py           # Entry point для worker
│   │   ├── task_worker.py        # Основной worker с очередью
│   │   └── playwright_service.py # Работа с headless браузером
│   └── __main__.py               # Entry point для бота
│
├── migrations/                    # Alembic миграции
│   └── versions/
│
├── tests/                         # Тесты
│   ├── unit/                     # Unit тесты
│   ├── integration/              # Integration тесты
│   └── fixtures/                 # Тестовые fixtures
│
├── features/                      # Документация фич (Feature Design)
│   ├── FEAT-0001-claude-auth-bot/
│   ├── FEAT-0001-telegram-bot-template/
│   └── FEAT-0002-code-quality-tools/
│
├── docs/                          # Дополнительная документация
├── examples/                      # Примеры использования
│
├── pyproject.toml                # Конфигурация проекта, ruff, mypy, pytest
├── Taskfile.yaml                 # Task runner команды
├── .pre-commit-config.yaml       # Pre-commit hooks
├── docker-compose.yml            # Docker окружение
├── Dockerfile                    # Образ для бота
├── Dockerfile.worker             # Образ для worker
└── alembic.ini                   # Конфигурация миграций

```

---

## Архитектурные подходы

### 1. Принципы "Функциональной ясности"

Проект строго следует принципам из `.claude/00-principles-functuonal-clearance.md`:

- **Ограниченная зона ответственности**: каждая функция/класс решает одну задачу (функции до 20-30 строк)
- **Явная обработка ошибок**: fail-fast, кастомные исключения с информативными сообщениями
- **Минимальные зависимости**: использование стандартной библиотеки, инкапсуляция внешних зависимостей
- **Современный Python**: Python 3.12+, async/await, type hints, pathlib, контекстные менеджеры
- **Предметно-ориентированное обобщение**: группировка по смысловому контексту, а не по технической схожести
- **Выразительные наименования**: понятные имена функций и переменных, отражающие предметную область
- **Тестируемость**: чистые функции, явные входы/выходы, изоляция side effects

### 2. Clean Architecture / Layered Architecture

```
┌────────────────────────────────┐
│   Presentation Layer           │  handlers/, filters/, middleware/
│   (Telegram API, Commands)     │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│   Service Layer                │  services/
│   (Business Logic)             │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│   Repository Layer             │  db/repositories/
│   (Data Access)                │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│   Database / External Services │  PostgreSQL, Playwright
└────────────────────────────────┘
```

**Принципы разделения:**
- Бизнес-логика изолирована от деталей инфраструктуры (Telegram API, БД)
- Repository Pattern для всех операций с БД
- Service Layer для бизнес-правил и координации
- Handlers остаются тонкими — только маршрутизация и валидация

### 3. Dependency Injection

Используется `punq` для управления зависимостями:

```python
# bot/core/container.py
container = punq.Container()
container.register(Settings, instance=settings)
container.register(Database, scope=punq.Scope.singleton)
```

**Преимущества:**
- Упрощение тестирования (легко мокировать зависимости)
- Явные зависимости (видно что требуется функции)
- Централизованное управление жизненным циклом объектов

### 4. Repository Pattern

Все операции с БД идут через репозитории:

```python
# bot/db/repositories/user_repository.py
class UserRepository:
    def __init__(self, database: Database):
        self.db = database

    async def get_by_id(self, user_id: int) -> dict | None:
        # SQL запрос через databases library
        ...
```

**Преимущества:**
- Чистое разделение бизнес-логики и SQL
- Легко подменить БД для тестов
- Явная обработка ошибок на уровне доступа к данным

### 5. Worker Pattern + Task Queue

```
Bot Service (aiogram)
    ↓
PostgreSQL Tasks Queue (FOR UPDATE SKIP LOCKED)
    ↓
Worker Service (1+ instances)
    ↓
Playwright (headless browser)
```

**Ключевые особенности:**
- Асинхронная обработка тяжелых задач (headless browser operations)
- Горизонтальное масштабирование workers
- PostgreSQL как очередь с `SELECT FOR UPDATE SKIP LOCKED`
- Retry механизм с экспоненциальной задержкой (2s, 4s, 8s)

### 6. PostgreSQL FSM Storage

Состояния FSM (Finite State Machine) для aiogram хранятся в PostgreSQL:

```python
# bot/db/fsm_storage.py
class PostgreSQLStorage(BaseStorage):
    """PostgreSQL-based FSM storage for aiogram."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_maker = session_maker
```

**Преимущества:**
- Персистентность состояний (сохраняются при перезапуске бота)
- Поддержка Topics через композитный ключ (chat_id, user_id, thread_id)
- Thread-safe конкурентный доступ
- Хранение данных в JSONB для гибкости

**Таблица FSM:**
- Композитный PRIMARY KEY: `(chat_id, user_id, thread_id)`
- Поле `state`: текущее состояние FSM (nullable)
- Поле `data`: JSONB для хранения данных состояния
- Автоматическое обновление `updated_at`

### 7. Изоляция браузерных сессий

Каждый chat_id имеет свою изолированную Playwright сессию:

```
/data/sessions/{chat_id}/
    ├── browser_context/
    └── cookies.json
```

**Безопасность:**
- Права доступа `700` (только владелец)
- Проверка chat_id при загрузке сессии
- Автоматическое удаление при истечении/ошибках

---

## Технологический стек

### Основные технологии

| Технология | Версия | Назначение |
|-----------|--------|------------|
| **Python** | 3.12+ | Основной язык |
| **aiogram** | 3.13+ | Telegram Bot framework (async) |
| **Playwright** | 1.40+ | Headless browser automation |
| **PostgreSQL** | 15+ | БД + очередь задач + FSM Storage |
| **SQLAlchemy** | 2.0+ | ORM (async) + FSM Storage |
| **Alembic** | 1.14+ | Database migrations |
| **asyncpg** | 0.30+ | Async PostgreSQL driver |
| **databases** | 0.9+ | Query builder (async) |
| **Pydantic** | 2.10+ | Data validation + Settings |
| **punq** | 0.7+ | Dependency Injection |
| **structlog** | 23.0+ | Structured logging |

### Dev Tools (Quality & Automation)

| Инструмент | Назначение |
|-----------|------------|
| **ruff** | Linter + Formatter (замена black, isort, flake8) |
| **mypy** | Static type checking |
| **prek** | Pre-commit hooks manager |
| **pytest** | Testing framework |
| **pytest-asyncio** | Async test support |
| **pytest-cov** | Coverage reporting |
| **Task** | Task runner (Taskfile.yaml) |
| **uv** | Fast package manager |

---

## Code Quality Tools

### 1. Pre-commit hooks (prek)

Файл: `.pre-commit-config.yaml`

**Хуки:**
- `trailing-whitespace` — удаление пробелов в конце строк
- `end-of-file-fixer` — пустая строка в конце файла
- `check-yaml` — валидация YAML
- `check-added-large-files` — защита от больших файлов
- `check-merge-conflict` — проверка merge conflicts
- `ruff` — автоматический fix проблем кода
- `ruff-format` — форматирование кода
- `mypy` — статическая проверка типов

**Установка:**
```bash
task prek:install
```

**Ручной запуск:**
```bash
task prek
```

### 2. Ruff (Linter + Formatter)

Файл: `pyproject.toml` → `[tool.ruff]`

**Конфигурация:**
- `target-version = "py312"` — поддержка Python 3.12+
- `line-length = 88` — стандартная длина строки
- Включенные правила:
  - `E` — pycodestyle errors
  - `W` — pycodestyle warnings
  - `F` — pyflakes
  - `I` — isort (сортировка импортов)
  - `B` — flake8-bugbear (находит багоподобные паттерны)
  - `C4` — flake8-comprehensions (оптимизация comprehensions)
  - `UP` — pyupgrade (современный синтаксис)

**Исключения:**
- `E501` — line too long (обрабатывается форматтером)
- `B008` — function calls in argument defaults (важно для aiogram DI)
- `C901` — complexity (хендлеры могут быть сложными)

**Использование:**
```bash
task format           # Автоформатирование
task lint:ruff        # Проверка без изменений
```

### 3. Mypy (Type Checking)

Файл: `pyproject.toml` → `[tool.mypy]`

**Конфигурация:**
- `python_version = "3.12"`
- `warn_return_any = true` — предупреждения о `Any` в возвращаемых значениях
- `check_untyped_defs = true` — проверка нетипизированных функций
- `no_implicit_optional = true` — явные `Optional`
- `disallow_untyped_defs = false` — разрешена частичная типизация (для хендлеров)
- `disallow_untyped_decorators = false` — важно для aiogram декораторов

**Ignore missing imports:**
- `aiogram.*`, `punq.*`, `databases.*`, `playwright.*`, `structlog.*`

**Использование:**
```bash
task lint:mypy
```

### 4. Pytest (Testing)

Файл: `pyproject.toml` → `[tool.pytest.ini_options]`

**Конфигурация:**
- `asyncio_mode = "auto"` — автоматическая поддержка async тестов
- Маркеры: `unit`, `integration`
- Coverage: `--cov=bot --cov-report=html`

**Использование:**
```bash
task test              # Все тесты
task test:unit         # Только unit
task test:integration  # Только integration
task coverage          # Тесты + coverage report
```

---

## Типичные команды разработки

### Установка и запуск

```bash
# Установка зависимостей
task install
# или: uv sync --group dev

# Настройка окружения
cp .env.example .env
# Отредактировать .env (добавить TELEGRAM_TOKEN, DATABASE_URL)

# Применить миграции
task db:upgrade

# Установить pre-commit hooks
task prek:install

# Запустить бота
task run
# или: python -m bot
```

### Разработка

```bash
# Форматирование кода
task format

# Проверка качества кода
task lint              # ruff + mypy
task lint:ruff         # только ruff
task lint:mypy         # только mypy

# Запуск тестов
task test
task test:unit
task coverage

# Полный QA цикл
task qa                # format + lint + coverage
```

### База данных

```bash
# Создать миграцию
task db:revision -- -m "add new table"

# Применить миграции
task db:upgrade

# Откатить миграцию
task db:downgrade

# Текущая версия
task db:current
```

### Очистка

```bash
# Удалить кеши и временные файлы
task clean
```

---

## Подход к документированию

### Features Directory

Каждая фича документируется в `features/FEAT-XXXX-название/`:

**Структура feature:**
```
features/FEAT-0001-claude-auth-bot/
├── README.md              # Полная спецификация фичи
│   ├── Problem Statement
│   ├── User Journeys
│   ├── Edge Cases
│   ├── Definition of Done
│   └── Technical Requirements
├── ARCHITECTURE.md        # Архитектурное решение (опционально)
└── review-request-changes/ # Code review результаты (опционально)
```

**User Journey подход:**
- Описание с точки зрения пользователя
- Step-by-step flow
- Starting point и End state
- Edge cases и Expected Behavior

**Definition of Done:**
- Must Have - Core Functionality
- Must Have - Error Handling
- Must Have - Security & Access Control
- Polish - UX
- Polish - DevOps
- Testing & Quality

---

## Принципы разработки (Style Guide)

См. `.claude/01-style-guide-functuonal-clearance.md`

### Ключевые правила

1. **Простые, однозадачные функции**
   - Каждая функция решает одну задачу
   - Длина не более 20-30 строк
   - Минимум побочных эффектов

2. **Явная обработка ошибок**
   - Fail-fast при невалидных данных
   - Кастомные классы исключений (`bot/core/exceptions.py`)
   - Подробные сообщения об ошибках
   - Избегаем лишних try/finally (используем context managers)

3. **Современный Python**
   - Type hints везде
   - Контекстные менеджеры вместо try/finally
   - `pathlib` вместо `os.path`
   - Async/await

4. **Документация**
   - Docstrings с описанием аргументов, результатов, ошибок
   - Комментарии для сложных алгоритмов, но не для очевидного кода
   - Говорящие имена функций и переменных

5. **Организация кода**
   - Группировка по функциональности, не по типу
   - Публичный API с четким интерфейсом
   - Приватные функции-помощники (`_helper_function`)

6. **Тестируемость**
   - Чистые функции, не зависящие от состояния
   - Изоляция side effects
   - Явные входные и выходные параметры
   - В тестах: `pytest.fail()` вместо `raise Exception()` (избегаем Error Hiding антипаттерна)

7. **Timeout как обязательная защита**
   - Все блокирующие операции должны иметь timeout
   - Все внешние вызовы должны иметь timeout
   - Timeout не должен маскировать логические ошибки

---

## Примеры паттернов из кодовой базы

### 1. Repository Pattern

```python
# bot/db/repositories/user_repository.py
class UserRepository:
    def __init__(self, database: Database):
        self.db = database

    async def get_by_id(self, user_id: int) -> dict | None:
        """
        Get user by Telegram user_id.

        Args:
            user_id: Telegram user_id

        Returns:
            User data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        query = "SELECT * FROM users WHERE id = :user_id"
        try:
            result = await self.db.fetch_one(query, {"user_id": user_id})
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}") from e
```

### 2. Service Layer с кешированием

```python
# bot/services/permission_service.py
class PermissionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache_ttl = settings.PERMISSION_CACHE_TTL
        self._cache: dict[str, tuple[bool, datetime]] = {}

    async def is_group_admin(self, bot: Bot, user_id: int, chat_id: int) -> bool:
        """Check if user is administrator with caching."""
        cache_key = f"{user_id}:{chat_id}"

        # Check cache
        if cache_key in self._cache:
            is_admin, cached_at = self._cache[cache_key]
            if self._is_cache_valid(cached_at):
                return is_admin

        # Query API
        member = await bot.get_chat_member(chat_id, user_id)
        is_admin = member.status in ["administrator", "creator"]

        # Update cache
        self._cache[cache_key] = (is_admin, datetime.utcnow())
        return is_admin
```

### 3. Явная валидация + Fail-fast

```python
# bot/handlers/claude_auth.py
def validate_email(email: str) -> bool:
    """Validate email format."""
    return bool(EMAIL_REGEX.match(email))

@router.message(Command("init_session"))
async def init_session_handler(message: Message, database: Database):
    # Parse command
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ Please provide an email address.")
        return

    email = parts[1].strip()

    # Fail-fast validation
    if not validate_email(email):
        await message.reply("❌ Invalid email format.")
        return

    # Continue processing...
```

---

## Окружение и деплой

### Docker Compose

Файл: `docker-compose.yml`

**Сервисы:**
- `postgres` — PostgreSQL 15
- `bot` — Telegram Bot service
- `worker` — Task Worker service (может масштабироваться)

**Volumes:**
- `/data/sessions` — браузерные сессии (персистентные)
- `/data/logs` — логи
- `postgres_data` — данные БД

### Environment Variables

Файл: `.env.example`

```bash
# Required
TELEGRAM_TOKEN=your_bot_token_here

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres/claude_bot

# Optional
LOG_LEVEL=INFO
DEBUG=False
PERMISSION_CACHE_TTL=300
```

---

## Контакты и поддержка

**Проект:** Shared Accounts / Claude Authorization Bot
**Статус:** Active Development
**Документация:** См. `README.md` и `features/`

---

**Версия документа:** 1.0
**Дата создания:** 2025-11-17
**Последнее обновление:** 2025-11-17
