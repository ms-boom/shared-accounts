---
argument-hint: [feature description]
description: Orchestrate Python/Use Case Layer feature implementation with architecture, coding, and review phases
---

# Task

You are orchestrating Python feature implementation using Use Case Layer architecture for: $ARGUMENTS

## Workflow

This is a multi-agent workflow with clear separation of concerns:

1. **usecase-architect** - Designs Use Case Layer architecture, creates plans (NO CODE, NO TESTS)
2. **python-implementer** - Writes Python code according to plan (NO TESTS)
3. **code-reviewer** - Runs tests, linters, finds issues, creates review files

## Implementation Loop

For EACH implementation stage:

### Step 1: Architecture
Launch **usecase-architect** agent to create/update architectural plan.

The architect will:
- Analyze existing Use Cases, Services, and Repositories
- Design proper layer separation
- Plan Unit of Work transaction boundaries
- Define session injection strategy
- Create DTO contracts
- Document migration strategy

### Step 2: Implementation
Launch **python-implementer** agent to write code according to plan.

INSTEAD you CAN run multiple **python-implementer** agents in PARALLEL to solve INDEPENDENT plan PARTS in a quick way.

The implementer will:
- Create DTOs (data contracts)
- Implement Repositories (data access)
- Implement Services (domain logic with session injection)
- Implement Use Cases (business coordination with UoW)
- Create thin Controllers (HTTP mapping only)
- Write background tasks (if needed)
- Create database migrations
- Write tests

### Step 3: Review
Launch **code-reviewer** agent to test and review implementation.

The reviewer will:
- Run all tests (pytest)
- Check layer separation
- Verify transaction boundaries
- Validate session injection
- Run linters (ruff, mypy)
- Check code formatting
- Create review files for issues

### Step 4: Fix or Complete
- **If code-reviewer found issues**: Return to Step 1 with review files
- **If no issues**: Mark stage as ✅ Complete

## Directory Structure

```
features/
  FEAT-[0-9]{4}-<name>/
    README.md                       # Feature requirements
    ARCHITECTURE.md                 # Architecture plan (usecase-architect)
    ARCHITECTURE_review_<N>.md      # Fix plan for review round N (usecase-architect)
    review-request-changes/         # Review findings (code-reviewer)
      0001-issue.md
      0001-issue.md_solved
      0002-issue.md
    .test-output/                  # Test results (code-reviewer)
      pytest-run.txt
      linter-output.txt
```

## Critical Rules

- **Separation of Concerns**: Each agent has ONE responsibility
  - Architect = Design only (layer separation, UoW, session injection)
  - Implementer = Code only (Use Cases, Services, DTOs, Controllers)
  - Reviewer = Test & review only

- **Layer Architecture Enforcement**:
  - Controllers are THIN (HTTP mapping only)
  - Use Cases manage transactions (Unit of Work)
  - Services use session injection
  - Repositories flush only, never commit
  - Integrations are stateless

- **Artifact Storage**: All files in `features/FEAT-[0-9]{4}-<name>/`

- **Loop Until Clean**: Continue until code-reviewer finds no issues

- **Agent Knowledge**: Each agent knows its responsibilities from its own .md file

## Example Feature Flow

### Feature: User Data Export

**Step 1 - Architecture** (usecase-architect):
```
Use Case: ExportUserDataUseCase
  - Request DTO: ExportUserDataRequest (user_id)
  - Response DTO: ExportUserDataResponse (export_id, status)
  - Transaction: Single UoW for atomicity

Service: UserDataExportService
  - Session injection: __init__(session: AsyncSession)
  - Methods: create_export(), get_export_status()

Repository: UserDataExportRepository
  - Data access only (flush, no commit)

Integration: DataArchiveClient
  - Stateless S3 client
  - No database dependency
```

**Step 2 - Implementation** (python-implementer):
- Create DTOs in `app/services/export/dto.py`
- Implement repository in `app/services/export/repository.py`
- Implement service in `app/services/export/service.py`
- Implement use case in `app/use_cases/export/export_user_data.py`
- Add controller in `app/api/v1/routers/export.py`
- Create migration: `task db:revision -- "Add user_data_export table"`
- Write tests in `tests/use_cases/test_export_user_data.py`

**Step 3 - Review** (code-reviewer):
- Run `task test`
- Check layer violations
- Verify UoW usage
- Validate session injection
- Run `task lint`

**Step 4 - Fix or Complete**:
- If issues found → create review files → return to Step 1
- If clean → Mark feature as ✅ Complete

## Quality Gates

Before marking feature complete, verify:

- [ ] All tests passing
- [ ] Layer separation maintained
- [ ] Transactions in Use Cases only
- [ ] Services use session injection
- [ ] Repositories flush only
- [ ] Controllers are thin
- [ ] Integrations stateless
- [ ] DTOs used for all data
- [ ] Type hints everywhere
- [ ] No linter errors
- [ ] Migrations tested
- [ ] Documentation updated
