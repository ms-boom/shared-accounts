# Testing Guide

## Архитектура тестовой инфраструктуры

Этот проект использует продвинутую систему организации тестов, основанную на паттернах из проекта intern-contest-cabinet. Система обеспечивает:

1. **Транзакционную изоляцию** - каждый тест работает в своей транзакции
2. **Savepoint паттерн** - фикстуры могут делать `commit()`, сохраняя изоляцию
3. **Session-scoped event loop** - один event loop для всех async фикстур
4. **Модульную организацию** - фикстуры разделены по функциональности

## Структура фикстур

```
tests/
├── fixtures/
│   ├── __init__.py
│   ├── environment.py    # Session-scoped event loop
│   └── database.py       # Database fixtures с транзакциями
├── conftest.py           # Загрузка модульных фикстур
└── pytest.ini            # Конфигурация pytest
```

### Порядок загрузки (критически важно!)

Фикстуры загружаются в строгом порядке в `conftest.py`:

```python
pytest_plugins = [
    "tests.fixtures.environment",  # ПЕРВЫМ - event loop
    "tests.fixtures.database",     # ВТОРЫМ - БД фикстуры
]
```

**Почему порядок важен:**
- `environment.py` создает session-scoped event loop
- Все async фикстуры должны использовать этот loop
- Если порядок нарушен, получите "got Future attached to a different loop"

## Доступные фикстуры

### Environment Fixtures (tests/fixtures/environment.py)

#### `event_loop` (scope=session)
Session-scoped event loop для всех async тестов и фикстур.

```python
def test_example(event_loop):
    # Event loop доступен для всех тестов
    pass
```

### Database Fixtures (tests/fixtures/database.py)

#### `test_settings` (scope=session)
Тестовая конфигурация с PostgreSQL и временными директориями.

```python
def test_with_settings(test_settings):
    assert test_settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert test_settings.DEBUG is True
```

#### `db_engine` (scope=session)
AsyncEngine для тестовой БД, переиспользуется между тестами.

```python
async def test_with_engine(db_engine):
    async with db_engine.connect() as conn:
        # Работа с движком
        pass
```

#### `db_connection` (scope=session)
Session-scoped connection с переконфигурацией Session.

```python
async def test_with_connection(db_connection):
    # Соединение сконфигурировано для изоляции
    pass
```

#### `db_transaction` (scope=function)
Function-scoped транзакция с автоматическим rollback после теста.

```python
async def test_with_transaction(db_transaction, db_session):
    # Все изменения будут откачены после теста
    pass
```

#### `db_savepoint` (scope=function)
Savepoint с автоматическим пересозданием после commit.

**Ключевая особенность:** Позволяет фикстурам делать `commit()` без нарушения изоляции.

```python
async def test_with_savepoint(db_savepoint, db_session):
    # Фикстуры могут делать commit()
    # Savepoint автоматически пересоздается
    pass
```

#### `db_sessionmaker` (scope=function)
async_sessionmaker для создания сессий в тестах.

```python
async def test_with_sessionmaker(db_sessionmaker):
    async with db_sessionmaker() as session:
        # Работа с сессией
        pass
```

#### `db_session` (scope=function)
**Самая популярная фикстура** - готовая AsyncSession для тестов.

```python
async def test_user_repository(db_session):
    from bot.db.models import User

    # Создаем пользователя
    user = User(id=12345, first_name="Test", username="testuser")
    db_session.add(user)
    await db_session.commit()

    # Проверяем
    result = await db_session.get(User, 12345)
    assert result.first_name == "Test"

    # После теста все откатится автоматически
```

#### `test_database` (scope=function)
Legacy фикстура для `databases.Database`. Сохранена для обратной совместимости.

**Внимание:** Создает НОВОЕ соединение вне транзакционного контекста. Не увидит uncommitted изменения из `db_session`.

```python
async def test_legacy(test_database):
    # Для старых тестов с databases library
    result = await test_database.fetch_one("SELECT 1 as value")
    assert result["value"] == 1
```

## Как работает транзакционная изоляция

### Архитектура

```
Session-scoped:
  event_loop
    ↓
  db_engine
    ↓
  db_connection (Session.configure)

Function-scoped (для каждого теста):
  db_transaction (BEGIN)
    ↓
  db_savepoint (SAVEPOINT)
    ↓
  db_session
    ↓
  [TEST RUNS]
    ↓
  ROLLBACK (автоматически)
```

### Пример работы

```python
# Тест 1
async def test_create_user(db_session):
    user = User(id=1, first_name="Alice")
    db_session.add(user)
    await db_session.commit()  # Commit в savepoint

    result = await db_session.get(User, 1)
    assert result is not None
    # После теста → ROLLBACK

# Тест 2
async def test_user_not_exists(db_session):
    result = await db_session.get(User, 1)
    assert result is None  # ✅ Пользователь из теста 1 откачен
```

### Savepoint Pattern

**Проблема:** Фикстуры могут делать `commit()`, что нарушает изоляцию.

**Решение:** Event listener автоматически пересоздает savepoint после каждого commit.

```python
# В фикстуре
async def create_test_user(db_session):
    user = User(id=999, first_name="Fixture User")
    db_session.add(user)
    await db_session.commit()  # ✅ Работает!
    return user

# В тесте
async def test_with_fixture_user(db_session, create_test_user):
    user = create_test_user
    # Фикстура сделала commit, но изоляция сохранена
    # После теста все откатится
```

## Миграции

### Применение миграций перед тестами

```bash
# Локально
alembic upgrade head

# В CI/CD
before_script:
  - alembic upgrade head
```

### Fixture `migrations` (ОПЦИОНАЛЬНО)

Фикстура существует, но **НЕ используется по умолчанию** для производительности.

```python
@pytest.fixture(scope="session")
def migrations(test_settings: Settings) -> None:
    """Run Alembic migrations for test database."""
    # Применяет миграции через alembic.command.upgrade
    pass

# Чтобы использовать, добавьте в db_engine:
@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings, migrations: None):
    # migrations будет выполнен перед созданием engine
    ...
```

## PostgreSQL для тестов

### Настройка

Проект использует PostgreSQL (не SQLite) для максимального соответствия production окружению.

```python
# tests/fixtures/database.py
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/claude_bot_test"
```

### Запуск PostgreSQL

```bash
# Docker
docker run -d \
  --name postgres-test \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=claude_bot_test \
  -p 5432:5432 \
  postgres:15

# Docker Compose
docker-compose up -d postgres
```

### Создание тестовой БД

```sql
CREATE DATABASE claude_bot_test;
```

## Запуск тестов

### Все тесты

```bash
pytest
```

### С покрытием

```bash
pytest --cov=bot --cov-report=html --cov-report=term-missing
```

### Только unit тесты

```bash
pytest -m unit
```

### Только integration тесты

```bash
pytest -m integration
```

### Конкретный тест

```bash
pytest tests/unit/test_user_repository.py::test_get_by_id
```

### Verbose режим

```bash
pytest -vv
```

### С SQL логами

Отредактируйте `tests/fixtures/database.py`:

```python
engine = create_async_engine(
    db_url,
    echo=True,  # ← Включить SQL логирование
    ...
)
```

## Написание тестов

### Unit Test (без БД)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.unit
async def test_permission_service():
    # Mock dependencies
    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=admin_member)

    # Test
    service = PermissionService(settings)
    result = await service.is_group_admin(bot, user_id, chat_id)

    assert result is True
```

### Integration Test (с БД)

```python
import pytest
from bot.db.models import User
from bot.db.repositories import UserRepository

@pytest.mark.integration
@pytest.mark.requires_db
async def test_user_repository_create(db_session):
    # Arrange
    repo = UserRepository(db_session)

    # Act
    user = User(id=12345, first_name="Test", username="testuser")
    db_session.add(user)
    await db_session.commit()

    # Assert
    result = await db_session.get(User, 12345)
    assert result is not None
    assert result.first_name == "Test"
```

### Фикстура с commit()

```python
@pytest.fixture
async def test_user(db_session):
    """Create test user with commit."""
    user = User(id=999, first_name="Fixture", username="fixture")
    db_session.add(user)
    await db_session.commit()  # ✅ Работает благодаря savepoint

    await db_session.refresh(user)
    return user

@pytest.mark.integration
async def test_with_user(db_session, test_user):
    # test_user создан через commit, но изоляция сохранена
    assert test_user.id == 999

    # После теста все откатится
```

## Частые проблемы и решения

### 1. "got Future attached to a different loop"

**Причина:** Нарушен порядок загрузки фикстур в `pytest_plugins`.

**Решение:**
```python
# conftest.py - ПРАВИЛЬНЫЙ порядок
pytest_plugins = [
    "tests.fixtures.environment",  # ПЕРВЫМ
    "tests.fixtures.database",     # ВТОРЫМ
]
```

### 2. "Connection pool exhausted"

**Причина:** Слишком много открытых соединений.

**Решение:** Проверьте настройки pool в `db_engine`:
```python
pool_size=3,
max_overflow=2,
```

### 3. Изменения из фикстур не видны в тестах

**Причина:** Используется `test_database` (legacy) вместо `db_session`.

**Решение:** Используйте `db_session` для всех операций:
```python
# ❌ НЕ ТАК
async def test_legacy(test_database):
    await test_database.execute(...)

# ✅ ТАК
async def test_modern(db_session):
    db_session.add(...)
    await db_session.commit()
```

### 4. Тесты падают с ошибками типизации

**Причина:** SQLAlchemy Session типизирован как `sessionmaker`, а не `async_sessionmaker`.

**Решение:** Используйте type ignore в фикстуре:
```python
return Session  # type: ignore[return-value]
```

### 5. "Database migrations not applied"

**Причина:** Миграции не применены перед запуском тестов.

**Решение:**
```bash
alembic upgrade head
pytest
```

## Best Practices

### 1. Всегда используйте `db_session`

```python
# ✅ Правильно
async def test_create_user(db_session):
    user = User(id=1, first_name="Test")
    db_session.add(user)
    await db_session.commit()

# ❌ Неправильно (legacy)
async def test_create_user(test_database):
    await test_database.execute("INSERT INTO users ...")
```

### 2. Маркируйте тесты

```python
@pytest.mark.unit
async def test_without_db():
    # Unit тест без БД
    pass

@pytest.mark.integration
@pytest.mark.requires_db
async def test_with_db(db_session):
    # Integration тест с БД
    pass
```

### 3. Используйте фикстуры для данных

```python
@pytest.fixture
async def admin_user(db_session):
    user = User(id=1, first_name="Admin", username="admin")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def test_admin_permissions(db_session, admin_user):
    # Используем готовые данные
    assert admin_user.username == "admin"
```

### 4. Очищайте состояние в фикстурах

```python
@pytest.fixture
async def clean_cache():
    cache = {}
    yield cache
    cache.clear()  # Очистка после теста
```

### 5. Используйте parametrize для множественных случаев

```python
@pytest.mark.parametrize("user_id,expected", [
    (1, True),
    (2, False),
    (999, None),
])
async def test_user_exists(db_session, user_id, expected):
    result = await db_session.get(User, user_id)
    assert (result is not None) == expected
```

## Дополнительные ресурсы

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [intern-contest-cabinet tests](../intern-contest-cabinet/tests/)

## Changelog

### 2025-11-17 - Initial version
- Перенос системы тестирования из intern-contest-cabinet
- Session-scoped event loop
- Транзакционная изоляция с savepoint pattern
- Модульная организация фикстур
- PostgreSQL вместо SQLite
- Обратная совместимость через `test_database` fixture
