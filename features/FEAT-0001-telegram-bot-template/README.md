# Feature: Telegram Bot Template with Group Management

## Problem Statement

Разработчикам телеграм-ботов нужен **готовый шаблон проекта**, который:
1. Объединяет лучшие практики из существующих проектов (trim-video-bot, chatgpt-telegram-bot)
2. Предоставляет **гибкую инфраструктуру** для работы с группами Telegram
3. Включает **примеры архитектурных паттернов** для типичных задач
4. Позволяет разработчику быстро начать и сфокусироваться на бизнес-логике

**Это НЕ готовый бот, а стартовый шаблон** - разработчик сам решает:
- Какие команды реализовать
- Как управлять доступом (в группе / приватном чате)
- Какую бизнес-логику добавить
- Какие данные хранить в БД

Текущая проблема: каждый раз при создании нового бота приходится заново настраивать инфраструктуру (DI, логирование, БД, обработка ошибок, FSM для контекста), что занимает много времени и может привести к ошибкам.

## User Persona

### Разработчик Telegram бота (Primary User)

**Контекст:**
- Хочет создать бота для работы в группах Telegram
- Знаком с Python и aiogram
- Не хочет тратить время на настройку инфраструктуры
- Нужны примеры архитектурных решений для типичных задач

**Потребности:**
- ✅ Готовая структура проекта с DI, БД, логированием
- ✅ Примеры работы с группами (проверка прав, контекст группы)
- ✅ FSM для управления состоянием диалогов
- ✅ Примеры двух паттернов управления: в группе и в приватном чате
- ✅ Документация с объяснением архитектурных решений
- ✅ Возможность легко добавлять свои команды и логику

**Примеры задач, которые решает разработчик:**
1. "Хочу чтобы бот в группе выполнял команды только от администраторов"
2. "Нужен приватный чат с ботом для настройки конкретной группы"
3. "Хочу сохранять состояние диалога (FSM) для сложных команд"
4. "Нужна БД для хранения настроек каждой группы"

## User Journeys

### Journey 1: Разработчик создает нового бота на основе шаблона

**Starting Point:**
Разработчик хочет создать нового Telegram бота для работы в группах.

**Step-by-Step Flow:**
1. Разработчик клонирует репозиторий `telegram-bot-template`
2. Видит четкую структуру проекта с README.md и ARCHITECTURE.md
3. Копирует `.env.example` в `.env` и заполняет `TELEGRAM_TOKEN`
4. Запускает `uv sync` для установки зависимостей
5. Запускает миграции БД: `alembic upgrade head`
6. Запускает бота: `python -m telegram_bot_template`
7. Бот успешно стартует, в логах видно успешную инициализацию всех сервисов
8. Добавляет бота в тестовую группу Telegram
9. Проверяет работу примеров команд `/start`, `/help`
10. Изучает `examples/` папку с паттернами
11. Начинает добавлять свою бизнес-логику

**End State:**
Разработчик имеет работающего бота с готовой инфраструктурой и понимает, куда добавлять код.

**Success Indicators:**
- От клонирования до первого запуска: < 5 минут
- Структура проекта интуитивно понятна
- Есть рабочие примеры для всех ключевых паттернов
- Документация отвечает на частые вопросы

---

### Journey 2: Разработчик добавляет команду с проверкой прав администратора (Пример паттерна)

**Задача:**
Разработчик хочет создать команду `/admin_action`, которая работает только для администраторов группы.

**Step-by-Step Flow:**

1. **Изучает пример в документации:**
   - Открывает `ARCHITECTURE.md` → раздел "Permission Management"
   - Видит готовый паттерн с использованием `PermissionService`

2. **Создает handler:**
   ```python
   # handlers/group_commands.py
   from telegram_bot_template.filters import IsGroupAdmin

   @router.message(Command("admin_action"), IsGroupAdmin())
   async def admin_action_handler(message: Message):
       await message.reply("Команда выполнена администратором")
   ```

3. **Использует готовый сервис проверки прав:**
   - `PermissionService` автоматически проверяет через Telegram API
   - Если пользователь не админ - команда игнорируется
   - Логирование автоматически фиксирует попытки доступа

4. **Тестирует:**
   - Администратор группы вызывает команду → работает
   - Обычный участник вызывает команду → игнорируется

**End State:**
Разработчик реализовал проверку прав за 5 минут без изучения Telegram API.

**Что предоставляет шаблон:**
- ✅ Готовый `PermissionService` с кешированием результатов
- ✅ Фильтр `IsGroupAdmin()` для aiogram
- ✅ Автоматическое логирование попыток доступа
- ✅ Примеры unit-тестов для проверки прав

---

### Journey 3: Разработчик реализует настройку группы через приватный чат с FSM (Пример паттерна)

**Задача:**
Разработчик хочет создать приватный диалог с ботом для настройки конкретной группы. Пользователь выбирает группу, и дальше все команды применяются к ней.

**Step-by-Step Flow:**

1. **Изучает пример FSM в документации:**
   - Открывает `examples/fsm_group_settings.py`
   - Видит готовую реализацию с выбором группы и сохранением контекста

2. **Использует готовый паттерн:**
   ```python
   # handlers/private_settings.py
   from telegram_bot_template.states import GroupSettingsStates
   from telegram_bot_template.services import GroupContextService

   @router.message(Command("configure"), StateFilter(None))
   async def start_configuration(message: Message, state: FSMContext):
       # Показываем список групп, где пользователь - админ
       groups = await group_service.get_admin_groups(message.from_user.id)
       await message.reply("Выберите группу:", reply_markup=groups_keyboard)
       await state.set_state(GroupSettingsStates.selecting_group)

   @router.callback_query(GroupSettingsStates.selecting_group)
   async def group_selected(callback: CallbackQuery, state: FSMContext):
       # Сохраняем выбранную группу в FSM контекст
       await state.update_data(selected_group_id=callback.data)
       await callback.message.edit_text("Группа выбрана. Используйте команды настройки.")
       await state.set_state(GroupSettingsStates.configuring)

   @router.message(Command("set_param"), GroupSettingsStates.configuring)
   async def set_parameter(message: Message, state: FSMContext):
       # Получаем группу из контекста
       data = await state.get_data()
       group_id = data["selected_group_id"]
       # Применяем настройку к выбранной группе
       await group_service.update_setting(group_id, ...)
   ```

3. **Тестирует диалог:**
   - Пользователь: `/configure` в приватном чате
   - Бот: показывает список групп с кнопками
   - Пользователь: выбирает группу
   - Бот: "Группа 'Моя группа' выбрана"
   - Пользователь: `/set_param value`
   - Бот: "Параметр обновлен для группы 'Моя группа'"

**End State:**
Разработчик реализовал полноценный диалог настройки с контекстом группы.

**Что предоставляет шаблон:**
- ✅ Готовые FSM states для работы с группами
- ✅ `GroupContextService` для управления выбранной группой
- ✅ Примеры клавиатур для выбора группы
- ✅ Middleware для автоматической проверки прав
- ✅ Примеры unit-тестов с FSM

---

### Journey 4: Разработчик реализует настройку бота прямо в группе (Второй паттерн)

**Задача:**
Разработчик хочет позволить администратору настраивать бота прямо в группе (публичные, безопасные настройки).

**Step-by-Step Flow:**

1. **Изучает пример в документации:**
   - Открывает `examples/group_settings.py`
   - Видит паттерн настройки в группе с проверкой прав

2. **Создает команду настройки в группе:**
   ```python
   # handlers/group_admin.py
   from telegram_bot_template.filters import IsGroupAdmin

   @router.message(Command("set_language"), IsGroupAdmin())
   async def set_language(message: Message, group_service: GroupService):
       # Команда работает только в группе, только для админов
       args = message.text.split()
       if len(args) < 2:
           await message.reply("Использование: /set_language <код языка>")
           return

       language = args[1]
       chat_id = message.chat.id

       # Сохраняем настройку для группы
       await group_service.update_language(chat_id, language)
       await message.reply(f"✅ Язык группы изменен на {language}")
   ```

3. **Выбирает какие настройки делать публичными:**
   - **В группе (публично):** язык, часовой пояс, формат вывода
   - **В приватном чате (скрыто):** API ключи, webhook URL, секреты

4. **Тестирует в группе:**
   - Администратор: `/set_language ru` в группе
   - Бот: "✅ Язык группы изменен на ru"
   - Обычный участник видит ответ (это публичная настройка)
   - Обычный участник пробует команду → игнорируется

**End State:**
Разработчик реализовал два паттерна управления: публичный (в группе) и приватный (в чате с ботом).

**Что предоставляет шаблон:**
- ✅ Примеры обоих паттернов с комментариями "когда использовать"
- ✅ Фильтры для разделения контекста (группа vs приватный чат)
- ✅ Готовые сервисы для работы с настройками группы
- ✅ Middleware для логирования всех изменений настроек

---

## Architectural Patterns & Edge Cases

Шаблон предоставляет готовые решения для типичных проблем при разработке ботов.

### Проверка прав доступа

| Scenario | Решение в шаблоне |
|----------|-------------------|
| Проверка администратора группы | `PermissionService` с кешированием результатов Telegram API (TTL: 5 мин) |
| Кеш устарел после изменения прав | Автоматическая инвалидация кеша при ошибках доступа |
| Бот не в группе (был удален) | `GroupService.verify_bot_membership()` при критичных операциях |
| Несколько администраторов одновременно | Транзакции БД с уровнем изоляции READ_COMMITTED |

### Управление состоянием (FSM)

| Scenario | Решение в шаблоне |
|----------|-------------------|
| Пользователь начал настройку, но не закончил | FSM state с TTL (24 часа), автоматический сброс |
| Пользователь в середине диалога использует другую команду | Middleware предлагает завершить текущий диалог или отменить |
| Хранение FSM state | Redis (prod) или MemoryStorage (dev) - настраивается в config |
| FSM state для разных групп | Используется `user_id + chat_id` как ключ |

### Работа с базой данных

| Scenario | Решение в шаблоне |
|----------|-------------------|
| БД недоступна при старте | Бот завершается с exit code 1 и понятной ошибкой в stdout |
| БД недоступна во время работы | Middleware ловит `DatabaseError`, отвечает пользователю, логирует в Sentry |
| Миграции не применены | `alembic check` в startup, fail-fast если версии не совпадают |
| Одновременное обновление записи | Пример с optimistic locking через `version` поле |
| Транзакции для связанных операций | Context manager `async with db.transaction()` |

### Обработка ошибок

| Scenario | Решение в шаблоне |
|----------|-------------------|
| Telegram API rate limit | Exponential backoff в `TelegramClientService` |
| Невалидные входные данные | Pydantic models + валидаторы, fail-fast в handler |
| Необработанное исключение в handler | Global exception handler → логирует в Sentry → отвечает пользователю |
| Telegram API недоступен | Circuit breaker pattern (опционально через env) |

---

## Definition of Done (DoD)

### Must Have (MVP) - Готовый шаблон проекта:

**Инфраструктура (из лучших практик trim-video-bot):**
- [ ] Структура проекта: handlers/ services/ db/ core/ migrations/ examples/
- [ ] Pydantic Settings с field validators для критичных параметров
- [ ] Dependency Injection через punq (контейнер + примеры регистрации)
- [ ] Structured logging: настраиваемые уровни, форматы, ротация файлов
- [ ] Типизация: mypy strict mode, все публичные функции типизированы
- [ ] Линтинг: ruff (pycodestyle, pyflakes, isort, bugbear, comprehensions)
- [ ] Lifecycle management: startup/shutdown hooks для сервисов
- [ ] Environment config: .env.example с описанием всех переменных

**База данных (из chatgpt-telegram-bot):**
- [ ] SQLAlchemy 2.0 + databases (async) для работы с БД
- [ ] Alembic для миграций с автогенерацией
- [ ] Примеры моделей: Group, User (минимальные для демонстрации)
- [ ] Repository pattern для изоляции работы с БД
- [ ] Примеры транзакций и optimistic locking

**Работа с группами Telegram (новое):**
- [ ] `PermissionService` - проверка прав администратора через API с кешированием
- [ ] Фильтры aiogram: `IsGroupAdmin()`, `IsPrivateChat()`, `IsGroup()`
- [ ] `GroupService` - базовые операции с группами (получить, обновить)
- [ ] Middleware для автоматической регистрации групп при взаимодействии
- [ ] Примеры обработки my_chat_member (бот добавлен/удален из группы)

**FSM для управления диалогами (новое):**
- [ ] Готовые State классы для типичных сценариев
- [ ] `GroupContextService` - управление выбранной группой в FSM
- [ ] Примеры FSM диалогов: выбор группы → настройка → подтверждение
- [ ] Конфигурация хранилища: Redis (prod) / Memory (dev)
- [ ] Middleware для обработки прерванных диалогов

**Примеры архитектурных паттернов:**
- [ ] `examples/permission_check.py` - проверка прав в группе
- [ ] `examples/fsm_group_settings.py` - диалог настройки через приватный чат
- [ ] `examples/group_settings.py` - настройка прямо в группе
- [ ] `examples/error_handling.py` - обработка ошибок и логирование
- [ ] `examples/database_operations.py` - транзакции, locking

**Документация:**
- [ ] README.md - быстрый старт, описание структуры, основные команды
- [ ] ARCHITECTURE.md - детальное описание архитектуры, принципы, паттерны
- [ ] Комментарии в примерах: "Когда использовать", "Почему так"
- [ ] .env.example с описанием каждой переменной и значениями по умолчанию
- [ ] CONTRIBUTING.md - как расширять шаблон своей логикой

**Тестирование:**
- [ ] Pytest конфигурация (asyncio_mode, markers, coverage)
- [ ] Примеры unit-тестов для сервисов (с моками Telegram API)
- [ ] Примеры integration-тестов для handlers (с тестовой БД)
- [ ] Фикстуры: bot, dispatcher, db_session, mock_telegram_api
- [ ] 100% покрытие примеров тестами (чтобы показать как)

**Качество кода:**
- [ ] Все примеры проходят mypy strict без ошибок
- [ ] Все примеры проходят ruff без warnings
- [ ] pre-commit hooks конфигурация (опционально для разработчика)
- [ ] Нет hardcoded значений, все через config

### Nice to Have (Enhancements):

**Developer Experience:**
- [ ] Docker Compose для быстрого старта (БД + Redis)
- [ ] Makefile с основными командами (install, migrate, test, lint)
- [ ] GitHub Actions CI шаблон (lint, test, build)
- [ ] Cookiecutter шаблон для инициализации нового проекта

**Расширенные примеры:**
- [ ] `examples/webhook_mode.py` - работа через webhook вместо polling
- [ ] `examples/rate_limiting.py` - защита от спама
- [ ] `examples/i18n.py` - поддержка нескольких языков
- [ ] `examples/background_tasks.py` - отложенные задачи (celery/rq)

**Мониторинг:**
- [ ] Sentry интеграция (опциональная через env)
- [ ] Prometheus метрики (опциональная через env)
- [ ] Health check handler для k8s/docker

**Дополнительные фичи:**
- [ ] Inline mode примеры
- [ ] Payment API примеры
- [ ] Media handling примеры (загрузка/скачивание файлов)

---

## Technical Architecture (High-Level)

### Структура шаблона проекта:

```
telegram_bot_template/
├── telegram_bot_template/     # Основной пакет
│   ├── handlers/              # Обработчики Telegram событий
│   │   ├── __init__.py
│   │   ├── common.py          # Общие команды (/start, /help)
│   │   └── group_admin.py     # ПРИМЕР: админ команды в группе
│   ├── services/              # Бизнес-логика
│   │   ├── group_service.py        # Управление группами (CRUD)
│   │   ├── permission_service.py   # Проверка прав доступа
│   │   ├── group_context_service.py # FSM контекст группы
│   │   └── user_service.py         # Управление пользователями
│   ├── db/                    # База данных
│   │   ├── models.py          # SQLAlchemy модели (Group, User)
│   │   ├── database.py        # Подключение к БД
│   │   └── repositories/      # Repository pattern
│   │       ├── group_repository.py
│   │       └── user_repository.py
│   ├── core/                  # Ядро приложения
│   │   ├── config.py          # Pydantic Settings
│   │   ├── container.py       # DI контейнер (punq)
│   │   ├── exceptions.py      # Кастомные исключения
│   │   └── logging.py         # Настройка логирования
│   ├── filters/               # Aiogram фильтры
│   │   ├── __init__.py
│   │   ├── is_group_admin.py  # Проверка админа группы
│   │   ├── is_private_chat.py # Только приватные чаты
│   │   └── is_group.py        # Только группы
│   ├── middleware/            # Middleware
│   │   ├── __init__.py
│   │   ├── error_handler.py   # Глобальная обработка ошибок
│   │   ├── group_tracker.py   # Авторегистрация групп
│   │   └── fsm_helper.py      # Помощь с прерванными диалогами
│   ├── states/                # FSM States
│   │   ├── __init__.py
│   │   └── group_settings.py  # States для настройки группы
│   └── bot.py                 # Точка входа
├── examples/                  # Примеры паттернов (НЕ работающий код)
│   ├── permission_check.py    # Как проверять права
│   ├── fsm_group_settings.py  # FSM диалог с выбором группы
│   ├── group_settings.py      # Настройка в группе vs приватный чат
│   ├── error_handling.py      # Обработка ошибок
│   └── database_operations.py # Транзакции, locking
├── migrations/                # Alembic миграции
│   └── versions/
├── tests/                     # Тесты (примеры)
│   ├── unit/                  # Unit-тесты сервисов
│   ├── integration/           # Integration-тесты handlers
│   └── fixtures/              # Фикстуры для тестов
├── .env.example               # Пример конфигурации
├── pyproject.toml             # Зависимости + настройки инструментов
├── alembic.ini                # Конфигурация миграций
├── README.md                  # Быстрый старт
├── ARCHITECTURE.md            # Детальное описание архитектуры
└── CONTRIBUTING.md            # Как расширять шаблон
```

### Ключевые архитектурные принципы:

1. **Separation of Concerns**
   - Handlers: только маршрутизация, минимум логики
   - Services: вся бизнес-логика
   - Repositories: изоляция работы с БД
   - Models: только структура данных

2. **Dependency Injection**
   - Все зависимости через punq контейнер
   - Легко подменять реализации для тестов
   - Явное управление lifecycle (startup/shutdown)

3. **Fail-Fast & Explicit Errors**
   - Валидация входных данных в начале функций
   - Pydantic models для структурированных данных
   - Кастомные исключения с понятными сообщениями
   - Никогда не "проглатываем" ошибки

4. **Type Safety**
   - mypy strict mode для всего кода
   - Все публичные функции типизированы
   - Современный Python синтаксис (3.12+)

5. **Testability**
   - Чистые функции без побочных эффектов
   - Моки для внешних зависимостей (Telegram API, БД)
   - Примеры тестов для каждого паттерна

6. **Extensibility**
   - Примеры (`examples/`) показывают как расширять
   - Документация объясняет "когда использовать"
   - Минимум магии, максимум явности

---

## Database Schema (Минимальная для демонстрации)

**Важно:** Это минимальная схема для демонстрации работы шаблона. Разработчик добавляет свои поля и таблицы под конкретные задачи.

### Table: `groups`

```sql
CREATE TABLE groups (
    id BIGINT PRIMARY KEY,              -- Telegram chat_id
    title VARCHAR(255),                 -- Название группы
    username VARCHAR(255),              -- Username группы (@group_name)
    type VARCHAR(50) NOT NULL,          -- 'group' или 'supergroup'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Дополнительные поля добавляет разработчик:
    -- enabled BOOLEAN DEFAULT FALSE,
    -- admin_only BOOLEAN DEFAULT FALSE,
    -- language VARCHAR(10) DEFAULT 'en',
    -- settings JSONB,  -- Для гибкости
);
```

**Зачем нужна эта таблица:**
- Отслеживать группы, где бот присутствует
- Сохранять метаданные группы (название может меняться)
- Хранить настройки, специфичные для каждой группы

### Table: `users`

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,              -- Telegram user_id
    username VARCHAR(255),              -- Username (@username)
    first_name VARCHAR(255),            -- Имя
    last_name VARCHAR(255),             -- Фамилия
    language_code VARCHAR(10),          -- Язык пользователя (из Telegram)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Дополнительные поля добавляет разработчик:
    -- is_banned BOOLEAN DEFAULT FALSE,
    -- premium BOOLEAN DEFAULT FALSE,
    -- preferences JSONB,
);
```

**Зачем нужна эта таблица:**
- Отслеживать пользователей бота
- Кешировать информацию профиля (не дергать API каждый раз)
- Хранить пользовательские настройки и состояние

### Индексы (примеры):

```sql
-- Быстрый поиск группы по username
CREATE INDEX idx_groups_username ON groups(username);

-- Быстрый поиск пользователя по username
CREATE INDEX idx_users_username ON users(username);

-- Для анализа активности
CREATE INDEX idx_groups_created_at ON groups(created_at);
CREATE INDEX idx_users_created_at ON users(created_at);
```

### Расширения (примеры для разработчика):

```sql
-- Если нужна связь many-to-many (например, избранные группы)
CREATE TABLE user_favorite_groups (
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, group_id)
);

-- Если нужна история действий
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    group_id BIGINT REFERENCES groups(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Философия схемы:**
- **Минимализм:** только самое необходимое для работы примеров
- **Гибкость:** разработчик добавляет поля под свои нужды
- **Примеры:** показываем типичные расширения в комментариях
- **Миграции:** все изменения через Alembic, откат поддерживается

---

## Handler Patterns (Примеры архитектуры)

Шаблон показывает **примеры** реализации типичных сценариев. Разработчик выбирает, что использовать.

### Паттерн 1: Базовая команда в группе

```python
# handlers/common.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="common")

@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    """Базовая команда доступная всем участникам."""
    await message.reply("Привет! Я бот-помощник.")
```

**Когда использовать:**
- Публичные команды доступные всем участникам группы
- Информационные команды (/help, /about, /stats)

### Паттерн 2: Команда только для администраторов группы

```python
# handlers/group_admin.py
from telegram_bot_template.filters import IsGroupAdmin
from telegram_bot_template.services import GroupService

router = Router(name="group_admin")

@router.message(Command("admin_action"), IsGroupAdmin())
async def admin_action(
    message: Message,
    group_service: GroupService  # Автоматически через DI
) -> None:
    """Команда доступная только администраторам группы."""
    chat_id = message.chat.id
    # Бизнес-логика через сервис
    result = await group_service.do_something(chat_id)
    await message.reply(f"Выполнено: {result}")
```

**Когда использовать:**
- Управление настройками бота в группе
- Модерация контента
- Админ-функции

### Паттерн 3: Настройка через приватный чат с FSM

```python
# handlers/private_settings.py
from aiogram.fsm.context import FSMContext
from telegram_bot_template.states import GroupSettingsStates
from telegram_bot_template.services import GroupContextService

router = Router(name="private_settings")

@router.message(Command("configure"), StateFilter(None))
async def start_configuration(
    message: Message,
    state: FSMContext,
    group_service: GroupService
) -> None:
    """Начало диалога настройки - выбор группы."""
    groups = await group_service.get_admin_groups(message.from_user.id)

    if not groups:
        await message.reply("Вы не администратор ни одной группы с этим ботом")
        return

    # Показываем клавиатуру с группами
    keyboard = create_groups_keyboard(groups)
    await message.reply("Выберите группу для настройки:", reply_markup=keyboard)
    await state.set_state(GroupSettingsStates.selecting_group)

@router.callback_query(GroupSettingsStates.selecting_group)
async def group_selected(
    callback: CallbackQuery,
    state: FSMContext,
    group_context: GroupContextService
) -> None:
    """Пользователь выбрал группу - сохраняем в контекст."""
    group_id = int(callback.data)

    # Сохраняем выбранную группу в FSM state
    await group_context.set_selected_group(state, group_id)
    await callback.message.edit_text("Группа выбрана. Используйте команды настройки.")
    await state.set_state(GroupSettingsStates.configuring)
```

**Когда использовать:**
- Многошаговые диалоги настройки
- Конфиденциальные настройки (скрытые от участников группы)
- Сложная конфигурация

### Паттерн 4: Обработка добавления/удаления бота из группы

```python
# handlers/group_events.py
from aiogram.types import ChatMemberUpdated

router = Router(name="group_events")

@router.my_chat_member()
async def on_bot_status_changed(
    event: ChatMemberUpdated,
    group_service: GroupService
) -> None:
    """Обработка добавления/удаления бота из группы."""
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    if new_status in ["member", "administrator"]:
        # Бот был добавлен в группу
        await group_service.register_group(event.chat)
        logger.info(f"Bot added to group {event.chat.id}")

    elif old_status in ["member", "administrator"] and new_status == "left":
        # Бот был удален из группы
        await group_service.mark_as_inactive(event.chat.id)
        logger.info(f"Bot removed from group {event.chat.id}")
```

**Когда использовать:**
- Автоматическая регистрация групп в БД
- Очистка данных при удалении бота
- Отслеживание жизненного цикла

---

**Важно:** Это примеры паттернов, а не требования. Разработчик:
- Выбирает какие паттерны использовать
- Добавляет свою валидацию и бизнес-логику
- Изменяет ответы под свою задачу

---

## Example Bot Flow (Демонстрация шаблона в действии)

Это пример того, как может выглядеть бот, созданный на основе шаблона. **Разработчик сам определяет команды и поведение.**

### Сценарий: Бот-помощник для управления опросами в группах

**1. Добавление бота в группу:**
```
[System] Бот "Poll Helper" добавлен в группу "Рабочий чат"
Бот: 👋 Привет! Используйте /help для списка команд.
```

**2. Создание опроса (команда только для админов):**
```
Администратор: /create_poll Где обедаем сегодня?

Бот: 📊 Опрос создан! Участники могут голосовать командой /vote.
```

**3. Настройка опроса через приватный чат (с FSM):**
```
Администратор → Приватный чат с ботом: /configure

Бот: Выберите группу для настройки:
[Кнопка] Рабочий чат
[Кнопка] Друзья

Администратор: [нажимает "Рабочий чат"]

Бот: Группа "Рабочий чат" выбрана.
Доступные настройки:
/set_poll_duration <минуты> - Длительность опросов
/set_anonymous <true|false> - Анонимность

Администратор: /set_poll_duration 60

Бот: ✅ Длительность опросов установлена: 60 минут
```

**Ключевые моменты примера:**
- ✅ Базовые команды доступны всем (/help, /vote)
- ✅ Админ-команды только для администраторов (/create_poll)
- ✅ Настройка через приватный чат с FSM (выбор группы → настройки)
- ✅ Все данные в БД (группы, пользователи, опросы)

**Что предоставил шаблон:**
- Инфраструктуру (DI, БД, логирование, FSM)
- Проверку прав (IsGroupAdmin фильтр)
- Работу с группами (GroupService)
- FSM для диалога настройки

**Что добавил разработчик:**
- Бизнес-логику опросов (PollService)
- Модели Poll, Vote в БД
- Специфичные команды (/create_poll, /vote)
- UI (клавиатуры для голосования)

---

## Architectural Decisions & Trade-offs

### Решения, принятые в шаблоне:

1. **✅ Кеширование прав администратора**
   - **Решение:** PermissionService с TTL-кешем (5 минут)
   - **Обоснование:** Баланс между безопасностью и нагрузкой на Telegram API
   - **Альтернатива:** Проверять каждый раз (безопаснее, но медленнее)

2. **✅ FSM хранилище: Redis (prod) / Memory (dev)**
   - **Решение:** Конфигурируемое через env переменную
   - **Обоснование:** Redis для production (персистентность), Memory для локальной разработки
   - **Trade-off:** Дополнительная зависимость (Redis) vs простота

3. **✅ Database: SQLAlchemy + databases (async)**
   - **Решение:** Как в chatgpt-telegram-bot
   - **Обоснование:** Async нативно работает с aiogram, готовые паттерны
   - **Альтернатива:** SQLAlchemy async (новее, но меньше примеров)

4. **✅ DI Container: punq**
   - **Решение:** Как в trim-video-bot
   - **Обоснование:** Простота, минимум магии, явная регистрация
   - **Альтернатива:** dependency-injector (больше функций, сложнее)

5. **✅ Обработка удаления бота из группы**
   - **Решение:** my_chat_member handler → пометка группы в БД
   - **Обоснование:** Сохраняем историю, можем анализировать
   - **Не удаляем данные сразу:** soft delete pattern

### Открытые вопросы (для разработчика шаблона):

1. **Rate limiting:**
   - Включить в MVP или сделать опциональным примером?
   - **Предложение:** Пример в `examples/rate_limiting.py`, не в core

2. **Internationalization (i18n):**
   - Встроить в шаблон или оставить для разработчика?
   - **Предложение:** Пример в `examples/i18n.py`, показать паттерн

3. **Webhook mode:**
   - Polling в MVP, webhook как пример?
   - **Предложение:** Polling работает из коробки, webhook в `examples/`

4. **Обновление метаданных группы:**
   - Обновлять title/username при каждом message?
   - **Предложение:** Middleware обновляет при обращении (не чаще 1 раза в час)

5. **Audit log:**
   - Логировать действия в БД или достаточно файлов?
   - **Предложение:** В MVP - structured logging, пример audit_log таблицы в комментариях

---

## Success Metrics (Критерии качества шаблона)

### Developer Experience (Первое впечатление):

- ✅ **Time to First Run < 5 минут** - от `git clone` до работающего бота
- ✅ **Zero Configuration** - работает с дефолтными настройками (SQLite, MemoryStorage)
- ✅ **Clear Structure** - разработчик понимает куда добавлять код без изучения документации
- ✅ **Examples Work** - все примеры в `examples/` запускаются и работают

### Code Quality (Технические метрики):

- ✅ **mypy strict: 100%** - все типы проверены, нет Any без необходимости
- ✅ **ruff: 0 warnings** - код соответствует PEP8 и best practices
- ✅ **Test Coverage > 90%** - высокое покрытие для демонстрации подхода
- ✅ **No Hardcoded Values** - все через config/env

### Documentation Quality:

- ✅ **README: Quick Start < 2 минуты чтения** - быстрый старт для нетерпеливых
- ✅ **ARCHITECTURE: Explains Why** - не просто "что", но и "почему так"
- ✅ **Comments in Examples** - "Когда использовать", "Альтернативы"
- ✅ **Migration Guide** - как перейти с другого фреймворка/шаблона

### Extensibility (Легкость расширения):

- ✅ **Add New Handler < 10 строк** - типичная задача минимально затратна
- ✅ **Add New Service** - понятно куда, как зарегистрировать в DI
- ✅ **Add New DB Model** - пример миграции в комментариях
- ✅ **Override Defaults** - можно заменить любой компонент

### Production Ready:

- ✅ **Error Handling** - все ошибки обработаны, логируются, не роняют бота
- ✅ **Graceful Shutdown** - корректное завершение (cleanup ресурсов)
- ✅ **Environment Aware** - dev/prod конфигурации
- ✅ **Docker Support** - опциональный Dockerfile и docker-compose

### Community Adoption (После релиза):

- 🎯 **GitHub Stars > 50** в первый месяц
- 🎯 **Issues: Response Time < 24h** - активная поддержка
- 🎯 **Real Projects Based On** - кто-то использует в production
- 🎯 **Pull Requests** - community contributions

---

## Ready for Implementation: YES ✅

### Что определено:

- ✅ **Problem Statement** - зачем нужен этот шаблон
- ✅ **User Persona** - кто будет использовать (разработчик)
- ✅ **User Journeys** - примеры использования шаблона
- ✅ **Architectural Patterns** - готовые решения для типичных задач
- ✅ **DoD Criteria** - детальный чеклист для MVP и enhancements
- ✅ **Technical Architecture** - структура проекта, принципы
- ✅ **Database Schema** - минимальная схема с примерами расширений
- ✅ **Handler Patterns** - примеры кода для разработчика
- ✅ **Success Metrics** - критерии качества шаблона

### Следующие шаги:

**Фаза 1: Architect Agent (Python Implementer)**
- Создать структуру проекта согласно Technical Architecture
- Реализовать core модули (config, container, logging, exceptions)
- Реализовать db модули (models, database, repositories)
- Реализовать services (GroupService, PermissionService, GroupContextService)
- Реализовать filters (IsGroupAdmin, IsPrivateChat, IsGroup)
- Реализовать middleware (error_handler, group_tracker, fsm_helper)
- Создать базовые handlers (common, group_admin, group_events)
- Настроить Alembic миграции
- Создать pyproject.toml с зависимостями
- Создать .env.example

**Фаза 2: Examples & Documentation**
- Создать примеры в `examples/` (permission_check, fsm_group_settings, etc.)
- Написать README.md (Quick Start)
- Написать ARCHITECTURE.md (детальное описание)
- Написать CONTRIBUTING.md (как расширять)
- Добавить комментарии в код ("Когда использовать", "Почему так")

**Фаза 3: Testing**
- Создать pytest конфигурацию
- Написать примеры unit-тестов для services
- Написать примеры integration-тестов для handlers
- Создать фикстуры (bot, db_session, mock_telegram_api)
- Достичь coverage > 90% для примеров

**Фаза 4: Developer Experience**
- Создать Docker Compose (опционально)
- Создать Makefile с командами (опционально)
- Проверить Time to First Run < 5 минут
- Проверить все критерии качества из Success Metrics

### Принципы реализации:

**Из "Функциональной ясности":**
1. Ограниченная зона ответственности - каждый модуль делает одно дело
2. Явная обработка ошибок - fail-fast, информативные сообщения
3. Минимальные зависимости - только необходимое
4. Выразительные наименования - код как документация
5. Немедленная валидация параметров - проверки в начале функций

**Из лучших практик проектов:**
- trim-video-bot: DI через punq, Pydantic Settings, mypy strict, ruff
- chatgpt-telegram-bot: работа с группами, роутеры, БД паттерны

**Дополнительно для шаблона:**
- Максимум комментариев и документации
- Код как учебный материал (читаемость > краткость)
- Примеры для всех типичных сценариев
- Гибкость и возможность расширения

---

## Appendix: Best Practices Integration

### Из trim-video-bot (Инфраструктура):

**✅ Берем:**

**Config & Settings:**
```python
# Pydantic Settings с field validators
class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = Field(description="Bot token from @BotFather")

    @field_validator("TELEGRAM_TOKEN")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("TELEGRAM_TOKEN is required")
        return value.strip()

    class Config:
        env_file = ".env"
```

**Dependency Injection:**
```python
# punq для явного DI
def create_container() -> punq.Container:
    container = punq.Container()
    container.register(Settings, instance=Settings())
    container.register(GroupService, scope=punq.Scope.singleton)
    return container
```

**Lifecycle Management:**
```python
async def startup_services(container):
    for service in [GroupService, PermissionService]:
        svc = container.resolve(service)
        if hasattr(svc, "startup"):
            await svc.startup()
```

**Structured Logging:**
```python
# Настраиваемые уровни, форматы, ротация
logging.basicConfig(
    level=settings.LOGGING_LEVEL,
    format=settings.LOGGING_FORMAT,
    handlers=[...],
)
```

**Типизация:**
- mypy strict mode для всего проекта
- Современный Python синтаксис (dict[str, Any], list[int], etc.)
- Аннотации для всех публичных функций

**Линтинг:**
- ruff (pycodestyle, pyflakes, isort, bugbear, comprehensions)
- Автоформатирование через ruff format

**❌ Не берем (не актуально для шаблона):**
- Работа с медиа файлами (ffmpeg, yt-dlp)
- Очереди обработки (QueueManager)
- TempFileManager (специфично для видео)
- YouTube integration

---

### Из chatgpt-telegram-bot (Работа с группами):

**✅ Берем:**

**Database Models:**
```python
# Модели для групп и пользователей
class Group(Base):
    id: int  # Telegram chat_id
    title: str
    type: str  # group/supergroup
    # ... разработчик добавляет свои поля

class User(Base):
    id: int  # Telegram user_id
    username: str | None
    # ...
```

**Роутеры:**
```python
# Разделение функционала по роутерам
admin_router = Router(name="admin")
message_router = Router(name="message")

dp.include_router(admin_router)
dp.include_router(message_router)
```

**Alembic Migrations:**
```bash
# Автогенерация миграций из моделей
alembic revision --autogenerate -m "Add groups table"
alembic upgrade head
```

**Middleware Pattern:**
```python
# Middleware для глобальной обработки
class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error: {e}")
            # ...
```

**❌ Не берем (не актуально для шаблона):**
- OpenAI интеграция (специфично для того бота)
- ChatHistory класс (специфичная бизнес-логика)
- Rollbar middleware (заменим на опциональный Sentry)
- Classifier prompt logic

---

### Новое (уникальное для шаблона):

**✅ Permission Management:**
```python
class PermissionService:
    """Проверка прав администратора с кешированием."""

    @cached(ttl=300)  # 5 минут
    async def is_group_admin(self, user_id: int, chat_id: int) -> bool:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
```

**✅ FSM для контекста группы:**
```python
class GroupContextService:
    """Управление выбранной группой в FSM state."""

    async def set_selected_group(self, state: FSMContext, group_id: int):
        await state.update_data(selected_group_id=group_id)

    async def get_selected_group(self, state: FSMContext) -> int | None:
        data = await state.get_data()
        return data.get("selected_group_id")
```

**✅ Filters для контекста:**
```python
class IsGroupAdmin(Filter):
    """Фильтр: только администраторы группы."""

    async def __call__(self, message: Message, permission_service: PermissionService):
        return await permission_service.is_group_admin(
            message.from_user.id,
            message.chat.id
        )
```

**✅ Group Lifecycle Events:**
```python
@router.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated):
    """Отслеживание добавления/удаления бота из группы."""
    # Автоматическая регистрация групп в БД
```

**✅ Examples & Documentation:**
- Папка `examples/` с рабочими примерами паттернов
- ARCHITECTURE.md с объяснением "почему"
- Комментарии "Когда использовать" в коде

**✅ Testing Patterns:**
- Фикстуры для моков Telegram API
- Примеры async тестов с БД
- Coverage как часть CI

---

### Философия интеграции:

1. **Инфраструктура** - из trim-video-bot (проверенная, надежная)
2. **Работа с Telegram** - из chatgpt-telegram-bot (паттерны групп)
3. **Примеры и обучение** - уникально для шаблона (максимум документации)
4. **Гибкость** - разработчик выбирает что использовать, что менять
