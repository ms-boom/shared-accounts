# Feature: FEAT-0002 - Code Quality Tools Setup

## Problem Statement

Telegram-bot-template нуждается в стандартизированной системе форматирования и проверки кода для обеспечения единого качества кодовой базы и упрощения разработки новых Telegram-ботов на основе этого шаблона. Необходимо внедрить проверенные инструменты из intern-contest-cabinet с адаптацией под специфику Telegram-ботов.

## Goals & Motivation

**Зачем это нужно:**
- Создать готовый к использованию шаблон с pre-configured инструментами качества кода
- Обеспечить единые стандарты кода во всех проектах, созданных на базе этого шаблона
- Упростить onboarding разработчиков через автоматизацию проверок
- Предотвратить типичные ошибки до попадания в репозиторий

**Какую проблему решаем:**
- Отсутствие стандартизации форматирования кода
- Невозможность автоматической проверки качества кода
- Риски human error при ручных проверках
- Несогласованность между разными проектами на Telegram-ботах

## User Journey

### Starting Point:
Разработчик создает новый Telegram-бот проект на основе telegram-bot-template

### Step-by-Step Flow:

1. **Клонирование шаблона**
   - Разработчик получает проект с уже настроенными `pyproject.toml`, `.pre-commit-config.yaml`, `Taskfile.yaml`
   - Видит в README инструкции по первичной настройке

2. **Первичная настройка**
   - Разработчик выполняет `task install` → устанавливаются все dev-зависимости (ruff, mypy, prek)
   - Выполняет `task prek:install` → устанавливаются git pre-commit хуки

3. **Разработка кода**
   - Пишет код для Telegram-бота
   - Перед коммитом выполняет `task format` для автоматического форматирования
   - Либо полагается на автоматические pre-commit hooks

4. **Проверка перед коммитом**
   - При попытке коммита автоматически срабатывают pre-commit хуки:
     - Ruff проверяет и исправляет код
     - Mypy проверяет типизацию
     - Базовые проверки (trailing whitespace, YAML syntax)
   - Если проверки падают → коммит отклоняется с понятными сообщениями об ошибках
   - Разработчик исправляет проблемы и повторяет коммит

5. **Continuous Integration**
   - В будущем: GitHub Actions автоматически запускает `task lint` и `task test`
   - Обеспечивается дополнительный уровень проверки качества

### End State:
Разработчик работает с проектом, где качество кода обеспечивается автоматически, минимизируя когнитивную нагрузку на ручные проверки.

## Technical Architecture

### Components to Implement

#### 1. **Ruff Configuration** (`pyproject.toml`)
Адаптированная версия из intern-contest-cabinet:

**Базовые настройки:**
- `target-version = "py312"` (Python 3.12+)
- `line-length = 88` (Black-compatible)
- Исключения: `alembic/`, `docs/` (если будут в будущем)

**Lint rules (адаптация для Telegram-ботов):**
- `E, W` - pycodestyle errors & warnings
- `F` - pyflakes (undefined names, unused imports)
- `I` - isort (import sorting)
- `B` - flake8-bugbear (common bugs)
- `C4` - flake8-comprehensions (list/dict comprehensions)
- `UP` - pyupgrade (modern Python syntax)

**Игнорируемые правила:**
- `E501` - line too long (обрабатывается форматером)
- `B008` - function calls in argument defaults (актуально для Telegram handlers)
- `C901` - complexity (чтобы не ограничивать логику хендлеров)

**Import sorting (isort):**
```toml
[tool.ruff.lint.isort]
known-first-party = ["bot"]  # Адаптировать под название проекта
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
split-on-trailing-comma = true
combine-as-imports = true
```

**Per-file ignores:**
```toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Unused imports в __init__.py допустимы
```

#### 2. **Mypy Configuration** (`pyproject.toml`)

**Базовые требования (упрощенные для Telegram-ботов):**
- `python_version = "3.12"`
- `warn_return_any = true`
- `warn_unused_configs = true`
- `check_untyped_defs = true` (проверка, но не требование типизации везде)
- `no_implicit_optional = true`
- `warn_redundant_casts = true`
- `warn_unused_ignores = true`

**Мягче, чем в intern-contest-cabinet:**
- `disallow_untyped_defs = false` (не требуем типизацию всех функций)
- `disallow_incomplete_defs = false` (частичная типизация допустима)
- `disallow_untyped_decorators = false` (важно для Telegram decorators)

**Обоснование упрощения:**
- Telegram-боты часто имеют много handler функций с динамическими параметрами
- Библиотеки aiogram/python-telegram-bot могут не иметь полной типизации
- Фокус на практичности для быстрой разработки ботов

**Ignore для внешних библиотек:**
```toml
[[tool.mypy.overrides]]
module = [
    "aiogram.*",  # Telegram bot framework
    "telebot.*",  # Alternative bot framework
    # Другие зависимости без stubs
]
ignore_missing_imports = true
```

#### 3. **Pre-commit Configuration** (`.pre-commit-config.yaml`)

**Структура:**

```yaml
repos:
  # 1. Basic file checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  # 2. Ruff (форматирование + линтинг)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        args: [--fix, --config=pyproject.toml]
      - id: ruff-format
        args: [--config=pyproject.toml]

  # 3. Mypy (опционально, может быть медленным)
  # Рекомендуется запускать через `task lint:mypy` вместо pre-commit
```

**Обоснование опциональности mypy в pre-commit:**
- Mypy может быть медленным на больших проектах
- Требует установки всех зависимостей
- Лучше запускать в CI/CD pipeline
- Оставляем возможность добавить позже

#### 4. **Taskfile.yaml**

**Адаптированная структура для Telegram-бота:**

```yaml
version: '3'

vars:
  PYTHON_SOURCE: bot  # Адаптировать под структуру проекта
  TEST_SOURCE: tests

tasks:
  default:
    desc: List available tasks
    cmds:
      - task --list

  # Development setup
  install:
    desc: Install development dependencies
    cmds:
      - uv sync --group dev

  # Code formatting
  format:
    desc: Format code with ruff
    cmds:
      - ruff check --fix {{.PYTHON_SOURCE}} {{.TEST_SOURCE}}
      - ruff format {{.PYTHON_SOURCE}} {{.TEST_SOURCE}}

  # Linting
  lint:
    desc: Run all linting tools
    cmds:
      - task: lint:ruff
      - task: lint:mypy

  lint:ruff:
    desc: Run ruff linter and formatter checks
    cmds:
      - ruff check {{.PYTHON_SOURCE}} {{.TEST_SOURCE}}
      - ruff format --check {{.PYTHON_SOURCE}} {{.TEST_SOURCE}}

  lint:mypy:
    desc: Run type checking with mypy
    cmds:
      - mypy {{.PYTHON_SOURCE}}

  # Testing
  test:
    desc: Run tests with pytest
    cmds:
      - pytest {{.CLI_ARGS}}

  test:unit:
    desc: Run unit tests only
    cmds:
      - pytest -m unit

  test:integration:
    desc: Run integration tests only
    cmds:
      - pytest -m integration

  coverage:
    desc: Run tests with coverage report
    cmds:
      - pytest --cov={{.PYTHON_SOURCE}} --cov-report=html --cov-report=term-missing

  # Pre-commit hooks
  prek:install:
    desc: Install pre-commit hooks
    cmds:
      - prek install

  prek:
    desc: Run pre-commit hooks manually
    cmds:
      - prek run --all-files

  prek:update:
    desc: Update pre-commit hooks to latest versions
    cmds:
      - prek autoupdate

  # Quality workflows
  check:
    desc: Run all quality checks (lint + test)
    cmds:
      - task: lint
      - task: test

  qa:
    desc: Full quality assurance (format + lint + test + coverage)
    cmds:
      - task: format
      - task: lint
      - task: coverage

  dev:
    desc: Development workflow (install + format + check)
    cmds:
      - task: install
      - task: format
      - task: check

  # Clean up
  clean:
    desc: Clean up temporary files and cache
    cmds:
      - find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
      - find . -type f -name "*.pyc" -delete
      - rm -rf .pytest_cache
      - rm -rf htmlcov
      - rm -rf .coverage
      - rm -rf .mypy_cache
      - rm -rf .ruff_cache
```

**Удалено из исходного Taskfile (специфично для intern-contest-cabinet):**
- Database tasks (`db:up`, `db:down`, `db:reset`, `db:revision`, etc.)
- Application runners (`run:web`, `run:api`, `run:worker`)
- Специфичные тесты (`test:user-service`, `test:auth`, etc.)

**Оставлено и адаптировано:**
- Development setup (`install`)
- Code quality (`format`, `lint`, `check`, `qa`)
- Testing basics (`test`, `test:unit`, `coverage`)
- Pre-commit management (`prek:*`)
- Clean up utilities

#### 5. **pyproject.toml - Dependency Groups**

```toml
[dependency-groups]
dev = [
    "ruff>=0.12.11",
    "mypy>=1.15.0",
    "prek>=0.1.6",
    "pytest>=8.4.1",
    "pytest-asyncio>=0.21.2",
    "pytest-cov>=6.2.1",
    "pytest-mock>=3.14.1",
    # Type stubs для популярных библиотек Telegram-ботов
    # "types-aiogram",  # Если используется aiogram
]
```

## Implementation Plan

### Phase 1: Configuration Files Setup

**Step 1.1: Create/Update pyproject.toml**
- [ ] Add `[tool.ruff]` section with adapted settings
- [ ] Add `[tool.ruff.format]` section
- [ ] Add `[tool.ruff.lint]` section with selected rules
- [ ] Add `[tool.ruff.lint.isort]` with project-specific `known-first-party`
- [ ] Add `[tool.ruff.lint.per-file-ignores]`
- [ ] Add `[tool.mypy]` section with relaxed settings
- [ ] Add `[[tool.mypy.overrides]]` for external libraries
- [ ] Add `[dependency-groups.dev]` with ruff, mypy, prek, pytest

**Step 1.2: Create .pre-commit-config.yaml**
- [ ] Add pre-commit-hooks repository (basic checks)
- [ ] Add ruff-pre-commit repository (ruff + ruff-format)
- [ ] Configure ruff hooks with `--config=pyproject.toml`
- [ ] Document why mypy is optional in pre-commit

**Step 1.3: Create Taskfile.yaml**
- [ ] Define `PYTHON_SOURCE` and `TEST_SOURCE` variables
- [ ] Add `install` task (uv sync --group dev)
- [ ] Add `format` task (ruff check --fix + ruff format)
- [ ] Add `lint` task (ruff + mypy)
- [ ] Add `test` tasks (pytest variants)
- [ ] Add `prek:*` tasks (install, run, update)
- [ ] Add `check`, `qa`, `dev` composite tasks
- [ ] Add `clean` task

### Phase 2: Documentation

**Step 2.1: Update README.md**
- [ ] Add "Development Setup" section with `task install` + `task prek:install`
- [ ] Add "Code Quality" section explaining ruff, mypy, prek
- [ ] Add "Available Commands" section with common `task` commands
- [ ] Add "Pre-commit Hooks" section explaining automatic checks

**Step 2.2: Create .github/CONTRIBUTING.md** (optional, для будущего)
- [ ] Code style guidelines
- [ ] How to run quality checks locally
- [ ] Pre-commit hook usage

### Phase 3: Initial Setup & Verification

**Step 3.1: Install Tools**
```bash
# В директории telegram-bot-template
uv sync --group dev
task prek:install
```

**Step 3.2: Verify Configuration**
```bash
# Проверка что ruff работает
task lint:ruff

# Проверка что mypy работает (может быть пустой проект)
task lint:mypy

# Проверка pre-commit хуков
task prek
```

**Step 3.3: Test on Sample Code** (when actual bot code appears)
- [ ] Create sample bot handler file
- [ ] Run `task format` → verify formatting
- [ ] Run `task lint` → verify no errors
- [ ] Make a test commit → verify pre-commit hooks work

### Phase 4: Template Finalization

**Step 4.1: .gitignore Updates**
- [ ] Add `.ruff_cache/`
- [ ] Add `.mypy_cache/`
- [ ] Add `htmlcov/`
- [ ] Add `.coverage`

**Step 4.2: Template Variables**
- [ ] Mark `PYTHON_SOURCE` in Taskfile as `# TODO: Update to your package name`
- [ ] Mark `known-first-party` in pyproject.toml as `# TODO: Update to your package name`
- [ ] Create template README section explaining these customization points

## Edge Cases & Behaviors

| Scenario | Expected Behavior |
|----------|-------------------|
| Разработчик пытается закоммитить неформатированный код | Pre-commit hook автоматически форматирует код ruff, разработчик делает `git add` и повторяет коммит |
| Mypy находит ошибки типов в pre-commit (если включен) | Коммит блокируется, разработчик видит понятное сообщение с указанием на проблемные строки |
| Проект использует другой package manager (не uv) | Taskfile.yaml легко адаптируется: `uv sync` → `pip install -e ".[dev]"` или `poetry install` |
| Разработчик хочет пропустить pre-commit hooks | Может использовать `git commit --no-verify`, но это не рекомендуется |
| Ruff конфликтует с существующим стилем кода | Благодаря пустому шаблону конфликтов не будет; в будущем: `task format` решает автоматически |
| YAML конфигурация невалидна | Pre-commit hook `check-yaml` отклонит коммит с понятным сообщением об ошибке |
| Большой файл добавлен по ошибке | Hook `check-added-large-files` предупредит разработчика |

## Definition of Done (DoD)

### Must Have:
- [ ] `pyproject.toml` содержит полные конфигурации `[tool.ruff]` и `[tool.mypy]`
- [ ] `pyproject.toml` содержит `[dependency-groups.dev]` с необходимыми инструментами
- [ ] `.pre-commit-config.yaml` создан и работает с ruff hooks
- [ ] `Taskfile.yaml` создан со всеми необходимыми tasks
- [ ] `.gitignore` обновлен для игнорирования cache директорий
- [ ] `task install` успешно устанавливает все dev-зависимости
- [ ] `task prek:install` успешно устанавливает git hooks
- [ ] `task format` и `task lint` работают без ошибок на пустом проекте
- [ ] Pre-commit hooks срабатывают при попытке коммита

### Polish:
- [ ] README.md содержит понятные инструкции по первичной настройке
- [ ] README.md содержит список доступных `task` команд с описаниями
- [ ] Конфигурационные файлы содержат комментарии для кастомизации
- [ ] Taskfile содержит комментарии с TODO для адаптации под конкретный проект

### Testing Criteria:
- [ ] Можно создать новый проект из шаблона и выполнить `task install` без ошибок
- [ ] Pre-commit hooks блокируют коммиты с проблемами форматирования
- [ ] `task format` автоматически исправляет стилистические проблемы
- [ ] `task lint` выявляет проблемы качества кода

## Adaptation Strategy (отличия от intern-contest-cabinet)

### 🔧 Упрощения для Telegram-ботов:

1. **Mypy - мягче:**
   - Не требуем полной типизации всех функций (`disallow_untyped_defs = false`)
   - Разрешаем частичную типизацию (`disallow_incomplete_defs = false`)
   - Разрешаем нетипизированные декораторы (критично для bot handlers)

2. **Ruff - прагматичнее:**
   - Сохраняем игнор `B008` (function calls in defaults) - важно для dependency injection в handlers
   - Сохраняем игнор `C901` (complexity) - bot handlers могут быть сложными

3. **Taskfile - минималистичнее:**
   - Убраны database tasks (не каждому боту нужна БД)
   - Убраны application runners (запуск бота - специфичен для каждого проекта)
   - Оставлен только универсальный инструментарий качества кода

4. **Pre-commit - быстрее:**
   - Mypy вынесен из pre-commit хуков (опционален, медленный)
   - Оставлены только быстрые проверки для комфортной работы

### ✅ Что осталось без изменений:

- Версии Python (3.12+)
- Line length (88)
- Базовый набор ruff правил (E, W, F, I, B, C4, UP)
- Import sorting стратегия (isort)
- Pre-commit базовые хуки (trailing-whitespace, end-of-file-fixer, etc.)
- Структура Taskfile commands (`format`, `lint`, `test`, etc.)

## Open Questions

- [ ] **Название пакета:** Какое будет дефолтное название для `PYTHON_SOURCE` в Taskfile? Предлагаю `bot`
- [ ] **Mypy в pre-commit:** Добавлять ли mypy в pre-commit hooks или оставить только для `task lint`? Рекомендация: оставить опциональным
- [ ] **GitHub Actions:** Создавать ли сразу `.github/workflows/ci.yml` для автоматических проверок в CI? Предлагаю отложить на отдельную фичу
- [ ] **Black vs Ruff format:** Оставить только ruff format или добавить black? Рекомендация: только ruff (black уже deprecated в пользу ruff)

## Success Metrics

**Количественные:**
- Все файлы конфигурации созданы: 3/3 (pyproject.toml, .pre-commit-config.yaml, Taskfile.yaml)
- Все базовые tasks работают: 10/10 (install, format, lint, test, prek, check, qa, dev, clean)
- Pre-commit hooks успешно установлены и работают

**Качественные:**
- Разработчик может склонировать шаблон и за 2 команды (`task install`, `task prek:install`) получить полностью настроенное окружение
- При попытке закоммитить плохо отформатированный код - коммит автоматически исправляется или блокируется с понятным сообщением
- Документация в README понятна для junior разработчика

---

## Ready for Implementation: ✅ Yes

**Следующий шаг:** Передать architect agent для технической реализации согласно этому плану.

**Изменения относительно исходного запроса:**
- Адаптированы настройки mypy (мягче) для специфики Telegram-ботов
- Упрощен Taskfile (убраны database/web tasks)
- Рекомендация: mypy вне pre-commit hooks для быстроты
- Добавлены TODO markers для кастомизации шаблона под конкретные проекты
