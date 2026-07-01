# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start the full stack (all 4 services)
docker compose up

# Rebuild and restart a single service after code changes
docker compose up --build backend
docker compose up --build frontend

# Access services
# Frontend health dashboard:  http://localhost:8501
# Backend API (Swagger):      http://localhost:8000/docs
# Database admin (Adminer):   http://localhost:8080
# Health endpoint:            http://localhost:8000/health
```

There are no test runners, linters, or build scripts. The backend uses `uvicorn --reload` for hot-reload in development.

## Architecture

This is a **FastAPI + PostgreSQL/pgvector + vanilla HTML** HR Q&A agent, orchestrated with Docker Compose.

**4 services** defined in `docker-compose.yml`:
- `db` — `pgvector/pgvector:pg16`, port 5432
- `backend` — FastAPI on Uvicorn, port 8000, depends on db healthy
- `frontend` — `python -m http.server 8501`, a single static `index.html` health dashboard
- `adminer` — DB management UI on port 8080, auto-connects to `db`

### Backend layered architecture

The backend follows **Controller → Service → Repository** layering:

```
api/v1/ (routes)  ──►  services/  ──►  repositories/  ──►  models/ + PostgreSQL
  thin — parse only     business logic     data access          persistence
```

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| Presentation | `app/api/v1/` | Thin route handlers — parse requests, call services, return responses. No business logic. |
| Business logic | `app/services/` | Stateless service classes orchestrating repositories, enforcing rules, calling external APIs. |
| Data access | `app/repositories/` | `BaseRepository[T]` with CRUD + entity-specific repos (e.g. `UserRepository`). Centralizes all SQL. |
| ORM models | `app/models/` | SQLAlchemy `DeclarativeBase` models — for querying only, not DDL. |
| Schemas | `app/schemas/` | Pydantic request/response models, split per domain. Separate from ORM models. |
| Cross-cutting | `app/core/` | Security (JWT/bcrypt), FastAPI dependencies, custom exceptions. |
| Infrastructure | `app/middleware/`, `app/tasks/` | Placeholders for future middleware and background workers. |
| Utilities | `app/utils/` | Seed data, helpers. |

**Startup sequence** (`backend/app/main.py` lifespan): `init_db()` → `seed_users()` → serve requests. The `init_db()` function enables the `vector` extension, then runs raw SQL `CREATE TABLE IF NOT EXISTS` statements — there is no migration framework. `seed_users()` inserts 4 demo users and is idempotent (skips if users already exist).

**Database** (`backend/app/database.py`): Dual connection approach — SQLAlchemy 2.0 async (`AsyncSessionLocal` for ORM operations via `get_db()`) and raw `asyncpg` connections (for DDL and direct queries via `get_db_connection()`). The ORM models in `app/models/models.py` mirror the raw DDL tables.

**5 tables** (all UUID PKs, TIMESTAMPTZ): `users`, `sessions`, `messages`, `feedback`, `hr_documents` (with `VECTOR(768)` embedding column and IVFFlat cosine index).

**Auth**: JWT-based with access tokens (1h, HS256) and refresh tokens (7d) via `python-jose`. Password hashing with passlib/bcrypt. The dependency `get_current_user()` in `app/core/deps.py` decodes the token, verifies `type=access`, and checks `is_active` on the user record. Routes: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh`. Auth business logic lives in `app/services/auth_service.py` — the route handlers in `app/api/v1/auth.py` are thin wrappers.

**Configuration** (`backend/app/config.py`): `pydantic-settings.BaseSettings` reads from `.env`. Requires `SECRET_KEY` ≥ 32 chars. The `.env` file is gitignored; `.env.example` is the template.

## Important patterns

- **Layered architecture**: All new features must follow the Controller → Service → Repository pattern. Routes in `api/v1/` are thin (parse → call service → return). Business logic goes in `services/`. Database queries go in `repositories/` (extend `BaseRepository[T]` from `app/repositories/base.py`). Services accept `AsyncSession` directly, not via FastAPI `Depends` — this keeps them usable from scripts/tasks.
- **No migration framework**: Tables are created at startup via raw SQL in `database.py`. Any schema change must go in the `create_tables()` function (use `IF NOT EXISTS` for idempotency). New columns need `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- **No ORM DDL**: The SQLAlchemy models in `app/models/models.py` are for querying only — they don't drive table creation.
- **Async everywhere**: All database access is async (`asyncpg` + SQLAlchemy async). Use `await` on all DB calls; sync code will block the event loop.
- **Spec-driven development**: Feature specs live in `.claude/specs/` and describe what to build before coding. The git history follows these specs: project setup → database schema → authentication → (next features).
- **Adminer Dracula theme**: `ADMINER_DESIGN=dracula` is set — don't change it without asking.

## Current state (what's wired vs. planned)

| Done | Not yet built |
|------|---------------|
| Docker environment | Chat/conversation endpoints |
| Database schema + seed data | Document ingestion (PDF/DOCX) |
| JWT auth (register/login/me/refresh) | RAG pipeline / vector search |
| Health endpoint (DB + Gemini check) | Message/feedback API endpoints |
| Google Gemini SDK installed | Tests, linting, CI/CD |

The `google-generativeai`, `PyPDF2`, and `python-docx` packages are installed but have no code calling them yet. The `messages`, `feedback`, and `hr_documents` tables exist but have no API endpoints.
