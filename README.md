# HR Q&A Agent

An AI-powered HR Q&A system built with **FastAPI**, **PostgreSQL/pgvector**, and **Google Gemini**. Employees ask HR questions in natural language and get instant, sourced answers via a Retrieval-Augmented Generation (RAG) pipeline — with streaming responses, conversation history, and an admin analytics dashboard.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│    Gemini    │
│  (nginx +    │     │  (FastAPI)   │     │   (LLM API)  │
│  vanilla JS) │     │              │     │              │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐     ┌──────────────┐
                     │  PostgreSQL  │     │   Adminer    │
                     │  + pgvector  │     │  (DB Admin)  │
                     └──────────────┘     └──────────────┘
```

**4 Docker services:**
| Service | Technology | Port | Purpose |
|---------|-----------|------|---------|
| `db` | pgvector/pgvector:pg16 | 5432 | Vector database with cosine similarity search |
| `backend` | FastAPI + Uvicorn | 8000 | REST API, RAG pipeline, SSE streaming |
| `frontend` | nginx:alpine | 80 | Static file serving + API proxy with SSE support |
| `adminer` | Adminer 4.8.1 | 8080 | Database management UI (Dracula theme) |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### Setup

1. **Clone and configure environment:**

```bash
git clone <repo-url>
cd hr-agent
cp .env.example .env
```

2. **Edit `.env` — set your Gemini API key and a strong secret key:**

```env
GEMINI_API_KEY=your_actual_gemini_api_key
SECRET_KEY=a_strong_random_secret_key_at_least_32_characters
```

3. **Start all services:**

```bash
docker compose up
```

4. **Access the application:**

| URL | Description |
|-----|-------------|
| http://localhost | Chat interface (login → ask questions) |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/health | Health check endpoint |
| http://localhost:8080 | Adminer (DB management) |

### Demo Users

Four users are seeded on first startup:

| Email | Password | Role | Department |
|-------|----------|------|-------------|
| `admin@company.com` | `password123` | hr_admin | HR |
| `john@company.com` | `password123` | employee | Engineering |
| `sarah@company.com` | `password123` | manager | Sales |
| `priya@company.com` | `password123` | employee | HR |

## Features

### Chat & Q&A
- **Streaming responses** — answers stream token-by-token via Server-Sent Events (SSE)
- **Source citations** — every answer includes the HR documents it drew from
- **Confidence scoring** — answers rated high/medium/low/none with visual badges
- **Context-aware follow-ups** — the system rewrites follow-up questions against conversation history (e.g., "What about vacation?" → "What is the company's vacation policy?")
- **Fallback handling** — gracefully responds when no relevant documents are found

### Document Management
- Upload HR policy documents (PDF, DOCX, TXT) via API
- Automatic chunking, embedding (Gemini `text-embedding-001`, 768-dim), and pgvector storage
- Access-level controls (`all`, `manager`, `hr_admin`)

### Session & Conversation Management
- Persistent chat sessions with auto-generated titles
- Session sidebar with create/rename/delete/clear
- 24-hour session expiry with background cleanup

### Feedback & Monitoring
- Thumbs-up/down feedback on every answer with reason capture
- Admin analytics dashboard with overview, feedback, query, and performance stats
- Structured JSON logging with X-Request-ID request tracing

### Security
- JWT-based authentication (access tokens 1h, refresh tokens 7d)
- bcrypt password hashing
- Role-based access control (employee, manager, hr_admin)

## API Endpoints

| Prefix | Key Endpoints |
|--------|--------------|
| `/api/v1/auth` | register, login, me, refresh |
| `/api/v1/documents` | upload, upload-bulk, list, stats, detail, delete |
| `/api/v1/search` | vector search, search health |
| `/api/v1/classify` | LLM-powered message classification |
| `/api/v1/query` | SSE streaming Q&A, test query, query health |
| `/api/v1/sessions` | CRUD, messages, clear-messages |
| `/api/v1/feedback` | submit feedback, get by message |
| `/api/v1/admin` | overview, feedback, query, performance, daily stats, logs |

Full interactive docs at http://localhost:8000/docs.

## Backend Architecture

The backend follows a **Controller → Service → Repository** layered pattern:

```
api/v1/ (routes)  ──►  services/  ──►  repositories/  ──►  models/ + PostgreSQL
  thin — parse only     business logic     data access          persistence
```

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| Presentation | `backend/app/api/v1/` | Thin route handlers — parse, call service, return response |
| Business Logic | `backend/app/services/` | Stateless services orchestrating repositories, calling Gemini |
| Data Access | `backend/app/repositories/` | `BaseRepository[T]` with CRUD + entity-specific queries |
| ORM Models | `backend/app/models/` | SQLAlchemy models (querying only, not DDL) |
| Schemas | `backend/app/schemas/` | Pydantic request/response models |
| Cross-cutting | `backend/app/core/` | Security, dependencies, exceptions, logging, cleanup |
| Prompts | `backend/app/prompts/` | LLM prompt templates (versionable, separate from logic) |

### RAG Pipeline

```
User Question
    │
    ▼
Query Classifier ──► policy | procedure | benefits | general_hr | off_topic | chitchat
    │
    ▼
Context Rewriter ──► rewrites follow-up questions using conversation history
    │
    ▼
Vector Retrieval ──► pgvector cosine similarity (top-k = 5, min score = 0.5)
    │
    ▼
Confidence Gate ──► high (≥0.75) | medium (≥0.50) | low (≥0.30) | none (<0.30)
    │
    ▼
Gemini Generation ──► streaming SSE response with sources & confidence
    │
    ▼
Message Storage ──► user message + assistant response saved to session
```

## Project Structure

```
hr-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Route handlers (8 routers)
│   │   ├── core/           # Security, deps, exceptions, logging, cleanup
│   │   ├── middleware/     # Request logging middleware
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── prompts/        # LLM prompt templates
│   │   ├── repositories/   # Data access layer
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic layer
│   │   └── utils/          # Seed data, document parsing, chunking, embeddings
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── index.html          # Single-page app (login + chat views)
│   ├── css/style.css       # Responsive styles
│   ├── js/                 # 7 vanilla JS modules (IIFE pattern)
│   │   ├── app.js          # App initialization & routing
│   │   ├── api.js          # HTTP client wrapper
│   │   ├── auth.js         # Login/register/token management
│   │   ├── chat.js         # Chat UI & message rendering
│   │   ├── streaming.js    # SSE stream consumption
│   │   ├── sessions.js     # Session sidebar CRUD
│   │   └── utils.js        # Helpers (formatting, sanitization)
│   ├── nginx.conf           # Static serving + /api/* proxy (SSE-compatible)
│   └── Dockerfile
├── database/
│   └── init.sql             # Reference DDL (6 tables, indexes, seed data)
├── docker-compose.yml       # 4-service orchestration
├── .env.example             # Configuration template
└── CLAUDE.md                # Developer guide
```

## Configuration

All settings are in `.env` (see `.env.example`). Key parameters:

| Setting | Default | Description |
|---------|---------|-------------|
| `CHUNK_SIZE` | 1000 | Document chunk size in characters |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `TOP_K_RETRIEVAL` | 5 | Number of document chunks retrieved per query |
| `MIN_RETRIEVAL_SCORE` | 0.5 | Minimum cosine similarity threshold |
| `HIGH_CONFIDENCE_THRESHOLD` | 0.75 | Threshold for "high" confidence badge |
| `SESSION_EXPIRY_HOURS` | 24 | Session TTL |
| `LOG_RETENTION_DAYS` | 30 | System log retention period |

## Development

```bash
# Rebuild and restart a single service after code changes
docker compose up --build backend
docker compose up --build frontend

# The backend uses uvicorn --reload for hot-reload in development
# Frontend files are served directly by nginx — refresh the browser
```

The backend starts up with this sequence: `init_db()` → `run_migrations()` → `seed_users()` → background cleanup tasks → serve requests. Tables are created via raw SQL (`CREATE TABLE IF NOT EXISTS`) — there is no migration framework. Schema changes are applied idempotently in `_run_migrations()`.

## Database

6 tables (all UUID PKs, TIMESTAMPTZ):

| Table | Purpose |
|-------|---------|
| `users` | Employee accounts with roles (employee/manager/hr_admin) |
| `sessions` | Chat sessions with 24h expiry |
| `messages` | Conversation history with sources, confidence, classification |
| `feedback` | Thumbs-up/down ratings with reasons |
| `system_logs` | Structured application logs (JSONB details) |
| `hr_documents` | Document chunks with pgvector embeddings (768-dim, IVFFlat index) |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend Framework | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 + pgvector |
| LLM | Google Gemini (embeddings + generation) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Reverse Proxy | nginx (Alpine) |
| Containerization | Docker Compose |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Streaming | Server-Sent Events (sse-starlette) |

## License

MIT
