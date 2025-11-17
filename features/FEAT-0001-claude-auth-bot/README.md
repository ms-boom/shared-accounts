# Feature: Claude Authorization Bot

**Feature ID:** FEAT-0001
**Status:** 📋 Ready for Implementation
**Created:** 2025-11-17
**Source Spec:** [docs/bot_spec.md](../../docs/bot_spec.md)

---

## Problem Statement

Пользователям Claude Code необходимо регулярно получать авторизационные коды через email-ссылки, что требует ручного открытия браузера, перехода по ссылкам и копирования кодов. Это отнимает время и прерывает рабочий процесс.

**Решение:** Telegram бот автоматизирует этот процесс, позволяя получать коды прямо в Telegram через простые команды, используя headless браузер для поддержания аутентифицированных сессий.

---

## User Journey

### Journey 1: Initial Setup (First-time per group/chat)

**Starting Point:**
Администратор добавил бота в Telegram группу или начал приватный чат с ботом.

**Step-by-Step Flow:**

1. **Admin видит**: Бот в списке участников группы, готов к взаимодействию

2. **Admin вводит команду**:
   ```
   /init_session user@example.com
   ```

3. **Бот отвечает**:
   ```
   🔄 Initializing session for user@example.com.
   Please wait for the authorization link request...
   ```

4. **Бот автоматически выполняет** (в фоне через Worker):
   - Создает изолированную браузерную сессию для этого chat_id
   - Открывает `https://claude.ai/login` в headless Chrome
   - Заполняет поле email
   - Нажимает "Continue with email"
   - Ждет страницу подтверждения "Check your email"

5. **Бот сообщает** (через ~5-10 секунд):
   ```
   📧 Email sent! Please send me the authorization link from your inbox.
   ```

6. **Admin получает письмо** от Claude на указанный email с ссылкой авторизации

7. **Admin копирует и отправляет боту ссылку**:
   ```
   https://claude.ai/login?token=abc123...
   ```

8. **Бот автоматически**:
   - Определяет, что это Claude login URL
   - Обновляет задачу с предоставленной ссылкой
   - Worker открывает ссылку в той же браузерной сессии
   - Проходит аутентификацию
   - Проверяет успешность (наличие элемента профиля пользователя)
   - Сохраняет аутентифицированную сессию на диск в `/data/sessions/{chat_id}/`
   - Записывает информацию в БД таблицу `chat_sessions`

9. **Бот подтверждает успех**:
   ```
   ✅ Session initialized successfully!
   You can now use `/get_code` to extract authorization codes.
   ```

**End State:**
Группа/чат имеет активную аутентифицированную сессию Claude, привязанную к указанному email. Все участники группы могут использовать `/get_code` для получения кодов.

---

### Journey 2: Getting Authorization Code (Regular usage)

**Starting Point:**
Пользователь работает с Claude Code и получил запрос на авторизацию с URL.

**Step-by-Step Flow:**

1. **User видит в Claude Code**: Запрос авторизации с URL вида:
   ```
   https://claude.ai/auth/authorize?client_id=...&redirect_uri=...
   ```

2. **User копирует URL и вводит в Telegram**:
   ```
   /get_code https://claude.ai/auth/authorize?client_id=...
   ```

3. **Бот мгновенно отвечает**:
   ```
   🔄 Extracting authorization code...
   ```

4. **Бот автоматически** (в фоне через Worker):
   - Проверяет наличие сессии для этого chat_id
   - Загружает сохраненный Playwright browser context
   - Открывает предоставленный auth URL
   - Ждет появления элемента с кодом (timeout: 30s)
   - Извлекает код авторизации (из `<code>` тега или `<input>` поля)
   - Обновляет статус задачи в БД
   - Обновляет last_used timestamp для сессии

5. **Бот отправляет результат** (через ~5-10 секунд):
   ```
   ✅ Authorization code: `ABC123XYZ789`
   ```
   (код в monospace для легкого копирования)

6. **User копирует код** одним кликом и вставляет в Claude Code

**End State:**
Пользователь получил авторизационный код и может продолжить работу с Claude Code. Весь процесс занял ~5-10 секунд вместо минут ручной работы с email и браузером.

---

### Journey 3: Health Check

**Starting Point:**
Пользователь или администратор хочет проверить статус бота и системы.

**Step-by-Step Flow:**

1. **User вводит**:
   ```
   /health
   ```

2. **Бот отвечает**:
   ```
   ✅ Bot Status:
   - Database: Connected
   - Active sessions: 3
   - Pending tasks: 1
   - Worker: Running
   ```

**End State:**
Пользователь понимает текущее состояние системы и может диагностировать проблемы при их наличии.

---

## Edge Cases & Behaviors

| Scenario | Expected Behavior |
|----------|-------------------|
| `/get_code` вызван без инициализированной сессии | **Bot:** `❌ No active session found for this chat. Run /init_session <email> first.` |
| Неверный формат email при `/init_session` | **Bot:** `❌ Invalid email format. Please provide a valid email address.` |
| Неверный формат URL при `/get_code` | **Bot:** `❌ Invalid auth URL format. Please provide a valid Claude authorization URL.` |
| Авторизационная ссылка устарела/невалидна | **Bot:** `❌ Authorization link is invalid or expired. Please run /init_session <email> again.` + задача помечена failed |
| Сетевая ошибка при загрузке страницы | **Bot:** `⚠️ Network error. Retrying... (attempt X/3)` → автоматические повторы с задержками 2s, 4s, 8s |
| Сетевая ошибка после 3 попыток | **Bot:** `❌ Network error persists after 3 attempts. Please try again later.` + полный лог ошибки в файл |
| Таймаут при ожидании элемента на странице (>30s) | **Bot:** `❌ Operation timed out. The page took too long to respond.` + скриншот страницы сохранен в `/data/errors/{task_id}.png` |
| Повторный `/init_session` для чата с активной сессией | **Bot:** `⚠️ Session already exists for this chat (email: existing@example.com). Do you want to replace it with user@example.com? Reply 'yes' to confirm.` |
| Браузерная сессия не найдена на диске (файлы повреждены) | **Bot:** `❌ Session file corrupted or missing. Please run /init_session <email> again.` + запись об ошибке удалена из БД |
| Несколько одновременных запросов `/get_code` от разных пользователей | Обрабатываются через очередь PostgreSQL последовательно с `SELECT FOR UPDATE SKIP LOCKED`, каждый пользователь получает свой код в порядке очереди |
| Worker service недоступен/упал | Задачи накапливаются в БД очереди со статусом `pending`, обрабатываются автоматически при восстановлении worker'а |
| Playwright не может найти элемент с кодом на странице | **Bot:** `❌ Could not extract authorization code. Page structure may have changed.` + скриншот страницы сохранен для отладки |
| PostgreSQL недоступна | **Bot:** `❌ Database connection error. Please contact administrator.` + попытки переподключения каждые 5 секунд |
| User отправляет невалидное сообщение (не команда, не URL) | Бот игнорирует (no reply), чтобы не спамить в групповых чатах |
| User отправляет URL не от Claude | Бот игнорирует или: `⚠️ This doesn't look like a Claude authorization link. Expected format: https://claude.ai/...` |

---

## Definition of Done (DoD)

### ✅ Must Have - Core Functionality

- [ ] **Command `/init_session <email>`** создает изолированную Playwright браузерную сессию для chat_id
- [ ] Бот автоматически заполняет email на странице `https://claude.ai/login`
- [ ] Бот автоматически нажимает кнопку "Continue with email"
- [ ] Бот корректно ожидает и детектирует страницу "Check your email"
- [ ] Бот распознает Claude login URL в сообщении пользователя
- [ ] Бот корректно обрабатывает авторизационную ссылку от пользователя
- [ ] Аутентифицированная сессия сохраняется на диск в `/data/sessions/{chat_id}/`
- [ ] Аутентифицированная сессия записывается в таблицу `chat_sessions` с полями: chat_id, email, session_path, created_at
- [ ] **Command `/get_code <url>`** загружает сохраненную браузерную сессию для chat_id
- [ ] Бот извлекает авторизационный код из страницы (из `<code>` тега или других элементов)
- [ ] Код возвращается пользователю в Telegram в течение 10 секунд при успехе
- [ ] **Command `/health`** возвращает статус: database, active sessions count, pending tasks, worker status
- [ ] PostgreSQL используется для очереди задач с query `SELECT FOR UPDATE SKIP LOCKED`
- [ ] Worker service обрабатывает задачи из очереди асинхронно
- [ ] Каждый chat_id имеет полностью изолированную браузерную сессию (нет cross-contamination)

### ✅ Must Have - Error Handling

- [ ] Все ошибки логируются в `/data/logs/bot.log` с полями: timestamp, level, task_id, chat_id, stacktrace
- [ ] Сетевые ошибки автоматически повторяются 3 раза с экспоненциальной задержкой (2s, 4s, 8s)
- [ ] Таймауты (>30s) возвращают понятное сообщение пользователю с описанием проблемы
- [ ] Невалидные/устаревшие ссылки детектируются и сообщаются пользователю с инструкцией
- [ ] Скриншоты страницы сохраняются в `/data/errors/{task_id}.png` при критических ошибках (timeout, extraction failed)
- [ ] Отсутствие сессии при `/get_code` возвращает понятную инструкцию о необходимости `/init_session`
- [ ] Невалидный формат email при `/init_session` возвращает ошибку до создания задачи
- [ ] Невалидный формат URL при `/get_code` возвращает ошибку до создания задачи
- [ ] При падении worker'а задачи не теряются и обрабатываются после восстановления

### ✅ Must Have - Database Schema

- [ ] Таблица `chat_sessions` создана с полями: chat_id (PK, bigint), email (text), session_path (text), created_at (timestamp), last_used (timestamp)
- [ ] Таблица `tasks` создана с полями: id (UUID PK), chat_id (bigint), user_id (bigint), task_type (text), payload (jsonb), status (text), result (text), created_at (timestamp), updated_at (timestamp)
- [ ] Индексы созданы для эффективных запросов: на tasks.status для выборки pending, на tasks.chat_id
- [ ] Очередь корректно обрабатывается при нескольких параллельных workers (`SKIP LOCKED` работает)
- [ ] Foreign key constraint от tasks.chat_id к chat_sessions.chat_id (optional, но желательно)

### ✅ Must Have - Security

- [ ] Browser profile directories имеют права доступа `700` (owner-only read/write/execute)
- [ ] Разные chat_id не могут получить доступ к сессиям друг друга (проверка chat_id при загрузке)
- [ ] Чувствительные данные (authorization codes, email) не логируются в plaintext
- [ ] Database credentials передаются через environment variables, не хардкодятся
- [ ] Telegram bot token передается через environment variable

### ✅ Polish - User Experience

- [ ] Эмодзи используются в сообщениях (🔄 для процесса, ✅ для успеха, ❌ для ошибок, ⚠️ для предупреждений, 📧 для email)
- [ ] Все сообщения об ошибках включают инструкции по исправлению (что делать дальше)
- [ ] Авторизационные коды форматируются в monospace (`` ` ``) для легкого копирования
- [ ] Сообщения краткие и понятные, избегают технического жаргона для обычных пользователей
- [ ] Статусные сообщения показывают прогресс ("Initializing...", "Extracting...", "Done!")

### ✅ Polish - Operations & DevOps

- [ ] `docker-compose.yml` конфигурация создана с сервисами: postgres, bot, worker
- [ ] Environment variables вынесены в `.env.example` файл с документацией
- [ ] Workers можно масштабировать горизонтально через `deploy.replicas` в docker-compose
- [ ] Structured logging настроен (structlog) с JSON форматом для удобного парсинга
- [ ] README.md содержит инструкции по запуску (Quick Start)
- [ ] Database migrations реализованы (через Alembic или встроенный механизм)
- [ ] Health checks endpoint `/health` доступен для мониторинга

### ✅ Testing & Quality

- [ ] Unit тесты для валидации email/URL форматов
- [ ] Integration тесты для полного цикла init_session → get_code
- [ ] Тесты для edge cases (таймауты, невалидные ссылки, отсутствие сессии)
- [ ] Тесты для concurrent task processing (SKIP LOCKED механизм)
- [ ] Manual test plan документирован для QA

---

## Technical Requirements Summary

### Stack

- **Python 3.11+** (современный синтаксис, type hints)
- **aiogram 3.x** — Telegram Bot framework (async)
- **Playwright** — headless browser automation (Chrome/Chromium)
- **PostgreSQL 15+** — task queue + session storage
- **asyncpg** — async PostgreSQL driver
- **pydantic 2.0+** — data validation
- **structlog 23.0+** — structured logging

### Architecture

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

### Key Configuration (Environment Variables)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Database
DATABASE_URL=postgresql://user:pass@localhost/claude_bot

# Paths
DATA_DIR=/data
SESSION_DIR=/data/sessions
LOG_DIR=/data/logs
ERROR_DIR=/data/errors

# Playwright
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT=30000  # 30 seconds

# Worker
WORKER_POLL_INTERVAL=1.0  # seconds
WORKER_RETRY_ATTEMPTS=3
WORKER_RETRY_BACKOFF=2,4,8  # seconds
```

### Database Schema

**Table: `chat_sessions`**
```sql
CREATE TABLE chat_sessions (
    chat_id BIGINT PRIMARY KEY,
    email TEXT NOT NULL,
    session_path TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP
);
```

**Table: `tasks`**
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    task_type TEXT NOT NULL,  -- 'init_session' | 'get_code'
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'processing' | 'done' | 'failed'
    result TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_status ON tasks(status) WHERE status = 'pending';
CREATE INDEX idx_tasks_chat_id ON tasks(chat_id);
```

**Queue Processing Query:**
```sql
SELECT * FROM tasks
WHERE status = 'pending'
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

---

## Open Questions & Future Considerations

### 🔍 Requires Clarification Before Implementation

1. **CSS Selectors для извлечения кода:**
   Точные CSS selectors для элемента с authorization code нужно определить после исследования актуальной структуры страницы `https://claude.ai/auth/authorize`.
   **Action:** Провести manual inspection страницы для определения селекторов.

2. **Session expiration detection:**
   Как определить, что сессия устарела? Нужно ли делать periodic health check сессий?
   **Options:**
   - Проверять при каждом `/get_code` и переинициализировать при ошибке
   - Отдельный background job проверяет все сессии раз в N часов

3. **Access control в private chats:**
   Текущая спецификация: "anyone who starts chat can use bot". Нужен ли whitelist пользователей по user_id?
   **Recommendation:** Начать без whitelist, добавить позже при необходимости.

4. **Session replacement confirmation:**
   При повторном `/init_session` требовать ли явное подтверждение от пользователя перед заменой сессии?
   **Proposed:** Да, запрашивать confirmation через inline keyboard или текстовое "yes".

### 💡 Future Enhancements (Not in MVP)

1. **Auto-detect expired sessions**
   Периодическая проверка валидности сохраненных сессий, уведомление пользователей об истечении.

2. **Multi-profile support**
   Возможность иметь несколько email/сессий на один chat_id (полезно для команд с разными аккаунтами).

3. **Admin commands:**
   - `/sessions` — список всех активных сессий с email и last_used
   - `/cleanup <days>` — удаление сессий неактивных N дней
   - `/stats` — статистика использования (кол-во запросов, success rate)

4. **Rate limiting:**
   Предотвращение abuse: ограничение на N запросов `/get_code` в минуту на chat_id.

5. **Webhook mode для Telegram:**
   Заменить long polling на webhooks для снижения latency и нагрузки.

6. **Metrics dashboard:**
   Prometheus + Grafana для мониторинга:
   - Request volume по командам
   - Success/failure rate
   - Average response time
   - Active sessions count

7. **Graceful session cleanup on bot removal:**
   Детектировать удаление бота из группы → автоматически удалять session и данные для этого chat_id.

---

## Handoff to Architecture & Implementation

**✅ Feature Brief Status:** Ready for Implementation

**Next Steps:**

1. **Architecture Design** — спроектировать детальную структуру кода:
   - Module organization (bot/, worker/, db/, models/)
   - Dependency injection для testability
   - Error handling hierarchy (custom exceptions)
   - Configuration management

2. **Implementation Plan** — разбить на incremental tasks:
   - Task 1: Database schema + migrations
   - Task 2: Bot service + basic commands (stub workers)
   - Task 3: Worker service + Playwright integration
   - Task 4: Error handling + logging
   - Task 5: Docker deployment + testing

3. **Code Review Checkpoints** — использовать `features/FEAT-0001-claude-auth-bot/review-request-changes/` для хранения результатов code review.

**Architect Agent Instructions:**

Design the architecture and implementation plan for this feature following the **"Functional Clarity"** principles (see `.claude/00-principles-functuonal-clearance.md`). The user journey and requirements above define the WHAT and WHY — now plan the HOW.

**Key Principles to Apply:**
- Ограниченная зона ответственности (каждая функция — одна задача)
- Явная обработка ошибок (fail-fast, информативные exception classes)
- Минимальные зависимости (инкапсуляция Playwright, PostgreSQL)
- Современный Python (3.11+, async/await, type hints)
- Тестируемость (чистые функции, изоляция side effects)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-17
**Author:** Feature Design Agent
**Approved By:** [Pending]
