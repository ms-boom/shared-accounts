# Руководство по ручной проверке Claude Authorization Bot

> Пошаговая инструкция для установки, настройки и проверки работоспособности бота на сервере.
> Всё собирается и запускается через Docker — установка Python, uv и зависимостей на хост не требуется.

---

## Содержание

1. [Требования к серверу](#1-требования-к-серверу)
2. [Установка и настройка](#2-установка-и-настройка)
3. [Запуск бота](#3-запуск-бота)
4. [Проверка базовой работоспособности](#4-проверка-базовой-работоспособности)
5. [Проверка команд Telegram](#5-проверка-команд-telegram)
6. [Проверка Topics (топиков)](#6-проверка-topics)
7. [Проверка CLI (внутри контейнера)](#7-проверка-cli)
8. [Проверка обработки ошибок](#8-проверка-обработки-ошибок)
9. [Проверка базы данных](#9-проверка-базы-данных)
10. [Проверка устойчивости](#10-проверка-устойчивости)
11. [Чеклист готовности к эксплуатации](#11-чеклист-готовности-к-эксплуатации)
12. [Устранение неполадок](#12-устранение-неполадок)

---

## 1. Требования к серверу

| Компонент | Требование |
|-----------|------------|
| ОС | Linux (Ubuntu 22.04+ / Debian 12+) |
| Docker | 20.10+ |
| Docker Compose | v2+ |
| RAM | минимум 512 MB (Playwright с Chromium) |
| Диск | минимум 1 GB свободного места |
| Сеть | доступ к api.telegram.org и claude.ai |

**Перед началом:**

- Получите Telegram Bot Token у [@BotFather](https://t.me/botfather)

---

## 2. Установка и настройка

### Шаг 2.1 — Клонирование репозитория

```bash
git clone <repo-url>
cd shared-accounts
```

### Шаг 2.2 — Настройка окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`, заполнив обязательное поле:

```env
# ОБЯЗАТЕЛЬНО: вставьте токен от @BotFather
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Остальные параметры можно оставить по умолчанию. Основные настройки для справки:

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `DATABASE_URL` | `sqlite+aiosqlite:////data/claude_bot.db` | Путь к БД внутри контейнера |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Таймаут браузера (мс) |
| `WORKER_RETRY_ATTEMPTS` | `3` | Количество повторных попыток |

### Шаг 2.3 — Сборка Docker-образа

```bash
docker-compose build
```

**Проверка:** сборка завершилась без ошибок. Миграции БД, установка Playwright и зависимостей — всё происходит автоматически внутри образа.

---

## 3. Запуск бота

```bash
docker-compose up -d
```

**Проверка запуска:**

```bash
docker-compose ps
# Столбец Status: Up
```

```bash
docker-compose logs -f bot
```

**Ожидаемые сообщения в логах:**

```
INFO     Starting Telegram Bot Template
INFO     Bot starting up...
INFO     Bot startup complete
INFO     Starting polling...
```

Если видите эти строки — бот запущен. Worker стартует автоматически в том же процессе.

Остановка: `docker-compose down`.

---

## 4. Проверка базовой работоспособности

### Шаг 4.1 — Проверка подключения к Telegram

Откройте чат с ботом в Telegram (личные сообщения). Отправьте:

```
/start
```

**Ожидаемый результат:** бот отвечает приветственным сообщением.

Если бот не отвечает — смотрите раздел [Устранение неполадок](#12-устранение-неполадок).

### Шаг 4.2 — Команда /health

Отправьте боту:

```
/health
```

**Ожидаемый ответ:**

```
✅ Bot Status

• Database: ✅ Connected
• Active sessions: 0
• Pending tasks: 0
• Worker: Running
```

**Что проверить:**
- Database: `✅ Connected` — БД доступна
- Active sessions: `0` — для свежей установки
- Pending tasks: `0` — очередь пуста

---

## 5. Проверка команд Telegram

### Подготовка: создайте тестовую группу

1. Создайте группу в Telegram
2. Добавьте бота в группу (достаточно прав на отправку сообщений)
3. Убедитесь, что вы — администратор группы (бот проверяет права вызывающего пользователя)

### Тест 5.1 — /init_session (инициализация сессии)

Отправьте в группе:

```
/init_session test@example.com
```

**Ожидаемый ответ (сразу):**

```
🔄 Initializing session for test@example.com.
Please wait for the authorization link request...
```

**Ожидаемый ответ (через 5–15 секунд, от worker'а):**
Сообщение об отправке email на указанный адрес, либо ошибка (если адрес невалидный для Claude).

**Что проверить в логах:**

```bash
docker-compose logs --tail=20 bot
```

Должны быть строки:

```
INFO     Created init_session task ... for chat .../0
INFO     Processing task ...: init_session
```

### Тест 5.1.1 — Проверка хранилища сессии на диске

После успешного выполнения `/init_session` бот создаёт браузерную сессию Playwright на диске.

**Структура хранения:**

```
/data/sessions/
└── {chat_id}/                     # Для основного чата (thread_id=0)
    └── state.json                 # Состояние браузера Playwright (~2-5 KB)

/data/sessions/
└── {chat_id}/
    └── {thread_id}/               # Для топика (thread_id > 0)
        └── state.json
```

- `state.json` — сериализованное состояние браузера (cookies, localStorage, sessionStorage). Это ключевой файл: без него последующие команды `/get_code` не смогут работать.
- Директории создаются с правами `0700` (доступ только владельцу).
- При ошибках Playwright дополнительно сохраняет скриншот `error_*.png` рядом с `state.json`.

**Проверка:**

```bash
# Узнать chat_id группы (из логов)
docker-compose logs bot | grep "Created init_session task"
# Пример: Created init_session task abc123 for chat 123456789/0

# Проверить что сессия создана
docker-compose exec bot ls -la /data/sessions/123456789/
# Должен быть файл state.json

# Проверить запись в БД
docker-compose exec bot sqlite3 /data/claude_bot.db \
  "SELECT chat_id, thread_id, email, session_path FROM chat_sessions"
# Должна быть строка с chat_id, email и путём к сессии
```

### Тест 5.2 — Полный сценарий успешной авторизации

Этот тест проверяет весь путь от инициализации сессии до получения кода. Для прохождения нужен **реальный email**, привязанный к аккаунту Claude.

#### Шаг 1. Инициализация сессии

```
/init_session your-real-email@example.com
```

**Ответ бота (сразу):**

```
🔄 Initializing session for your-real-email@example.com.
Please wait for the authorization link request...
```

> Что делает бот: worker запускает headless-браузер Playwright, открывает https://claude.ai/login, вводит email и нажимает "Continue with email". Claude отправляет письмо на указанный адрес.

**Ответ бота (через 5–15 секунд):**

```
✅ 📧 Email sent! Please send me the authorization link from your inbox.
```

Если вместо этого пришла ошибка — проверьте логи: `docker-compose logs --tail=30 bot`.

#### Шаг 2. Отправка login-ссылки из email

Откройте почту, найдите письмо от Claude. Скопируйте ссылку вида:

```
https://claude.ai/login?token=xyz...
```

Вставьте её в чат **как обычное сообщение** (без команды):

```
https://claude.ai/login?token=abc123def456...
```

**Ответ бота (сразу):**

```
🔄 Processing login link...
```

> Что делает бот: автоматически распознаёт URL как login-ссылку Claude. Worker открывает браузер с сохранённой сессией, переходит по ссылке и ждёт появления пользовательского меню — это означает что авторизация прошла успешно. Обновлённое состояние браузера (cookies, tokens) сохраняется в `state.json`.

**Ответ бота (через 5–15 секунд):**

```
✅ Session initialized successfully! You can now use /get_code.
```

#### Шаг 3. Получение кода авторизации

Теперь сессия активна. Когда Claude Code запросит авторизацию, он покажет URL вида:

```
https://claude.ai/auth/authorize?client_id=...&redirect_uri=...
```

Отправьте этот URL боту:

```
/get_code https://claude.ai/auth/authorize?client_id=...&redirect_uri=...
```

**Ответ бота (сразу):**

```
🔄 Extracting authorization code...
```

> Что делает бот: worker открывает браузер с авторизованной сессией, переходит по auth URL. На странице Claude отображает код авторизации. Бот находит его на странице (ищет элемент `<code>`, `[data-testid="auth-code"]` и другие варианты) и извлекает текст.

**Ответ бота (через 5–15 секунд):**

```
✅ Authorization code: ABC123XYZ789
```

#### Шаг 4. Использование кода

Скопируйте полученный код и вставьте его в Claude Code. Авторизация завершена.

#### Полная последовательность сообщений

```
Вы:    /init_session user@example.com
Бот:   🔄 Initializing session for user@example.com...
Бот:   ✅ 📧 Email sent! Please send me the authorization link from your inbox.

[Вы проверяете почту, копируете ссылку]

Вы:    https://claude.ai/login?token=xyz...
Бот:   🔄 Processing login link...
Бот:   ✅ Session initialized successfully! You can now use /get_code.

[Claude Code показывает auth URL]

Вы:    /get_code https://claude.ai/auth/authorize?client_id=...
Бот:   🔄 Extracting authorization code...
Бот:   ✅ Authorization code: ABC123XYZ789

[Вы вставляете код в Claude Code]
```

---

### Тест 5.3 — /init_session без email

```
/init_session
```

**Ожидаемый ответ:**

```
❌ Please provide an email address.

Usage: /init_session user@example.com
```

### Тест 5.4 — /init_session с невалидным email

```
/init_session не-email
```

**Ожидаемый ответ:**

```
❌ Invalid email format. Please provide a valid email address.
```

### Тест 5.5 — /init_session от не-администратора

Попросите обычного участника группы (без прав администратора) отправить:

```
/init_session user@example.com
```

**Ожидаемый ответ:**

```
❌ Only group administrators can initialize sessions.
Please contact your group admin.
```

### Тест 5.6 — /get_code без активной сессии

```
/get_code https://claude.ai/auth/authorize?client_id=test
```

**Ожидаемый ответ:**

```
❌ No active session found for this chat.

Run /init_session <email> first to initialize a session.
```

### Тест 5.7 — /get_code без URL

```
/get_code
```

**Ожидаемый ответ:**

```
❌ Please provide the Claude authorization URL.

Usage: /get_code https://claude.ai/auth/authorize?...
```

### Тест 5.8 — /get_code с невалидным URL

```
/get_code https://google.com
```

**Ожидаемый ответ:**

```
❌ Invalid auth URL format. Please provide a valid Claude authorization URL.

Expected format: https://claude.ai/auth/authorize?...
```

### Тест 5.9 — /health после создания задач

```
/health
```

**Проверить:**
- `Pending tasks` может быть >0 (если задачи ещё обрабатываются)
- `Active sessions` отражает созданные сессии

---

## 6. Проверка Topics

> Требуется супергруппа с включёнными топиками.

### Подготовка

1. Конвертируйте группу в супергруппу (Настройки группы → Тип группы)
2. Включите Topics (Настройки → Topics → On)
3. Создайте тестовый топик, например: "Тестирование"

### Тест 6.1 — Сессия в основном чате

Отправьте в General (основной чат):

```
/init_session main@example.com
```

**Ожидаемый результат:** бот принял команду, задача создана.

### Тест 6.2 — Сессия в топике

Перейдите в топик "Тестирование" и отправьте:

```
/init_session topic@example.com
```

**Ожидаемый результат:** бот принял команду, создана отдельная задача.

### Тест 6.3 — Проверка изоляции

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db \
  "SELECT chat_id, thread_id, task_type, payload FROM tasks ORDER BY created_at DESC LIMIT 5"
```

**Ожидаемый результат:** две записи с разными `thread_id` и разными email в `payload`.

---

## 7. Проверка CLI

CLI запускается внутри контейнера через `docker-compose exec`.

### Тест 7.1 — Справка CLI

```bash
docker-compose exec bot uv run python -m core.cli --help
```

**Ожидаемый результат:** список доступных команд (`account`, `health`).

### Тест 7.2 — Health через CLI

```bash
docker-compose exec bot uv run python -m core.cli health
```

**Ожидаемый результат:**

```
✅ System Health Status

✅ Database: CONNECTED
✅ Active sessions: ...
✅ Pending tasks: ...

✅ All systems operational
```

### Тест 7.3 — Список сессий

```bash
docker-compose exec bot uv run python -m core.cli account list-chats
```

**Ожидаемый результат:** таблица с chat_id, thread_id, email всех активных сессий (или пустая таблица для свежей установки).

---

## 8. Проверка обработки ошибок

### Тест 8.1 — Бот корректно обрабатывает ошибки Playwright

Вызовите `/init_session` с реальным email. Если Playwright не сможет открыть страницу Claude (например, из-за сети), worker должен:

1. Отправить сообщение об ошибке в чат
2. Записать ошибку в лог

**Проверка скриншотов ошибок:**

```bash
docker-compose exec bot ls /data/errors/
```

### Тест 8.2 — Повторные попытки (retry)

Worker автоматически повторяет неудачные задачи до 3 раз с задержками 2с, 4с, 8с.

**Проверка в логах:**

```bash
docker-compose logs bot | grep -i "retry\|attempt\|failed"
```

### Тест 8.3 — Бот не падает после ошибок

После серии ошибочных команд отправьте:

```
/health
```

**Ожидаемый результат:** бот отвечает, `Database: ✅ Connected`.

---

## 9. Проверка базы данных

### Тест 9.1 — Таблицы существуют

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db ".tables"
```

**Ожидаемый результат:** список таблиц включает `chat_sessions`, `groups`, `tasks`, `users`, `alembic_version`.

### Тест 9.2 — WAL-режим включён

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db "PRAGMA journal_mode"
```

**Ожидаемый результат:** `wal`

### Тест 9.3 — Нет зависших задач

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db "
SELECT status, COUNT(*) as count
FROM tasks
GROUP BY status
"
```

**Ожидаемый результат:** нет записей со статусом `processing` (если worker работает корректно и все задачи обработаны).

### Тест 9.4 — Размер БД

```bash
docker-compose exec bot du -h /data/claude_bot.db*
```

**Ожидаемый результат:** основной файл < 10 MB для свежей установки.

---

## 10. Проверка устойчивости

### Тест 10.1 — Перезапуск контейнера

```bash
docker-compose restart bot
```

Подождите 10 секунд, отправьте `/health` боту.

**Ожидаемый результат:** бот отвечает, данные (сессии, БД) сохранились.

### Тест 10.2 — Полная остановка и запуск

```bash
docker-compose down
docker-compose up -d
```

Отправьте `/health`.

**Ожидаемый результат:** бот работает, данные на месте (volume `bot_data` сохраняет состояние).

### Тест 10.3 — Проверка данных после перезапуска

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db \
  "SELECT COUNT(*) FROM tasks"
```

**Ожидаемый результат:** количество задач совпадает с тем, что было до перезапуска.

---

## 11. Чеклист готовности к эксплуатации

### Установка и конфигурация

- [ ] `.env` настроен с корректным `TELEGRAM_TOKEN`
- [ ] Docker-образ собран без ошибок
- [ ] Контейнер стартует и бот выходит на polling

### Базовая работоспособность

- [ ] Бот отвечает на `/start`
- [ ] `/health` возвращает `Database: ✅ Connected`
- [ ] Worker виден в логах

### Команды Telegram

- [ ] `/init_session email` — создаёт задачу, worker обрабатывает
- [ ] `/init_session` без аргументов — сообщение об ошибке
- [ ] `/init_session невалидный-email` — сообщение об ошибке
- [ ] `/init_session` от не-админа — отказ в доступе
- [ ] `/get_code` без сессии — понятное сообщение
- [ ] `/get_code` с невалидным URL — сообщение об ошибке
- [ ] `/health` — показывает актуальную статистику

### Topics

- [ ] Сессии в разных топиках изолированы (разные `thread_id` в БД)

### CLI

- [ ] `health` через CLI — показывает статус системы
- [ ] `account list-chats` через CLI — список сессий

### База данных

- [ ] Таблицы созданы
- [ ] WAL-режим включён
- [ ] Нет зависших задач (`status=processing`)

### Устойчивость

- [ ] Данные сохраняются после перезапуска контейнера
- [ ] Бот не падает после серии ошибочных команд
- [ ] Нет критических ошибок в логах при нормальной работе

---

## 12. Устранение неполадок

### Бот не отвечает на сообщения

1. Проверьте логи: `docker-compose logs -f bot`
2. Убедитесь что `TELEGRAM_TOKEN` в `.env` верный
3. Проверьте что бот добавлен в группу и имеет права на отправку сообщений
4. Проверьте доступ к `api.telegram.org` с сервера: `curl -s https://api.telegram.org`

### Database: ❌ Disconnected

1. Проверьте логи на ошибки миграций: `docker-compose logs bot | grep -i "alembic\|migration\|database"`
2. Пересоздайте контейнер: `docker-compose down && docker-compose up -d`

### Playwright не запускается

1. Проверьте свободное место на диске: `df -h`
2. Ищите zombie-процессы внутри контейнера: `docker-compose exec bot ps aux | grep chromium`
3. Перезапустите контейнер: `docker-compose restart bot`

### Задачи зависают (status=processing)

```bash
docker-compose exec bot sqlite3 /data/claude_bot.db \
  "SELECT id, task_type, status, updated_at FROM tasks WHERE status='processing'"
```

Worker автоматически сбрасывает задачи, зависшие более 5 минут. Если не помогает — перезапустите контейнер.

### Topics не работают

1. Убедитесь что группа — супергруппа (не обычная группа)
2. Проверьте что Topics включены в настройках группы
3. Отправляйте команды внутри топика, не в General

### Нехватка места на диске

```bash
# Проверить размер данных внутри контейнера
docker-compose exec bot du -sh /data/*

# Очистить старые скриншоты ошибок
docker-compose exec bot rm -f /data/errors/*.png

# Очистить завершённые задачи старше 30 дней
docker-compose exec bot sqlite3 /data/claude_bot.db \
  "DELETE FROM tasks WHERE status IN ('completed','failed') AND created_at < datetime('now','-30 days')"
```
