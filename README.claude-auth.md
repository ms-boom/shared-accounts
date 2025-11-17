# Claude Authorization Bot

Автоматизированный Telegram бот для получения авторизационных кодов Claude через headless браузер.

## Возможности

- **Автоматическая авторизация** в Claude.ai через headless Playwright browser
- **Изолированные сессии** для каждого чата/группы
- **Очередь задач** с PostgreSQL и worker service
- **Проверка прав доступа** - только администраторы могут инициализировать сессии
- **Обработка ошибок** с автоматическими повторами и скриншотами
- **Health check** для мониторинга состояния системы

## Быстрый старт

### Prerequisites

- Docker & Docker Compose
- Telegram Bot Token от [@BotFather](https://t.me/botfather)

### Установка

1. **Клонируйте репозиторий**
   ```bash
   git clone <repo-url>
   cd shared-accounts
   ```

2. **Настройте environment**
   ```bash
   cp .env.example .env
   # Отредактируйте .env и добавьте TELEGRAM_TOKEN
   ```

3. **Запустите через Docker Compose**
   ```bash
   docker-compose up -d
   ```

   Это запустит:
   - PostgreSQL database
   - Telegram bot service
   - Worker service с Playwright
   - Database migrations

4. **Проверьте статус**
   ```bash
   docker-compose ps
   docker-compose logs -f bot worker
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

## Архитектура

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

## База данных

### Таблицы

**`chat_sessions`** - хранит Playwright сессии для каждого чата
- `chat_id` (PK) - Telegram chat_id
- `email` - email адрес Claude аккаунта
- `session_path` - путь к данным сессии Playwright
- `created_at` - когда сессия создана
- `last_used` - последнее использование

**`tasks`** - очередь фоновых задач
- `id` (UUID PK) - уникальный ID задачи
- `chat_id` - Telegram chat_id
- `user_id` - Telegram user_id инициатора
- `task_type` - тип задачи: `init_session`, `get_code`
- `payload` (JSONB) - данные задачи
- `status` - статус: `pending`, `processing`, `done`, `failed`
- `result` - результат или сообщение об ошибке
- `created_at`, `updated_at`

### Миграции

```bash
# Применить миграции
docker-compose exec bot alembic upgrade head

# Создать новую миграцию
docker-compose exec bot alembic revision --autogenerate -m "description"

# Откатить миграцию
docker-compose exec bot alembic downgrade -1
```

## Разработка

### Локальный запуск без Docker

1. **Установите зависимости**
   ```bash
   uv sync --group dev
   ```

2. **Установите Playwright browsers**
   ```bash
   uv run playwright install chromium
   ```

3. **Запустите PostgreSQL**
   ```bash
   docker run -d \
     -p 5432:5432 \
     -e POSTGRES_DB=claude_bot \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=postgres \
     postgres:15-alpine
   ```

4. **Примените миграции**
   ```bash
   uv run alembic upgrade head
   ```

5. **Запустите bot и worker в разных терминалах**
   ```bash
   # Terminal 1: Bot
   uv run python -m bot

   # Terminal 2: Worker
   uv run python -m bot.worker
   ```

### Code Quality

```bash
# Форматирование кода
uv run ruff format bot tests

# Линтинг
uv run ruff check --fix bot tests

# Type checking
uv run mypy bot

# Запуск тестов
uv run pytest

# Запуск тестов с coverage
uv run pytest --cov=bot
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

### Рекомендации

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
   ```yaml
   # docker-compose.yml
   worker:
     deploy:
       replicas: 3
   ```

## Принципы "Функциональной ясности"

Проект следует принципам:

- **Ограниченная зона ответственности** - каждая функция делает одно дело
- **Явная обработка ошибок** - fail-fast с информативными сообщениями
- **Минимальные зависимости** - только необходимые библиотеки
- **Современный Python** - Python 3.12+, type hints, async/await
- **Тестируемость** - чистые функции, изоляция side effects

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
