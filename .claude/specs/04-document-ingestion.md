# Feature 4: Document Ingestion Pipeline (Updated Architecture)

## 1. Overview

Build the document ingestion pipeline that takes HR policy documents (PDF, DOCX, TXT), parses them, splits into chunks, generates embeddings using Gemini `gemini-embedding-001`, and stores them in PostgreSQL with pgvector.

This establishes the **knowledge base** for the HR Q&A Agent.

---

## 2. Depends on

- **Feature 1: Project Setup & Docker Environment**
- **Feature 2: Database Schema & Migrations**
- **Feature 3: User Authentication**

---

## 3. Routes

| Method | Path | Auth Required | Role Required | Description |
|--------|------|---------------|---------------|-------------|
| `POST` | `/api/v1/documents/upload` | Yes (JWT) | `hr_admin` | Upload and ingest a document |
| `POST` | `/api/v1/documents/upload-bulk` | Yes (JWT) | `hr_admin` | Upload multiple documents |
| `GET` | `/api/v1/documents` | Yes (JWT) | `hr_admin` | List all ingested documents |
| `GET` | `/api/v1/documents/{source}` | Yes (JWT) | `hr_admin` | Get document chunks |
| `DELETE` | `/api/v1/documents/{source}` | Yes (JWT) | `hr_admin` | Delete all chunks from a source |
| `GET` | `/api/v1/documents/stats` | Yes (JWT) | `hr_admin` | Get ingestion statistics |

---

## 4. Route Specifications

*(Same as original Feature 4, but paths now prefixed with `/api/v1/`)*

### A. `POST /api/v1/documents/upload`

**Request:** Multipart form with `file` (PDF/DOCX/TXT, max 20MB) and `access_level` (default: `all`)

**Success Response (201):**
```json
{
  "message": "Document ingested successfully",
  "source": "remote_work_policy_2024.pdf",
  "chunks_created": 24,
  "total_chars": 14520,
  "access_level": "all"
}
```

### B. `POST /api/v1/documents/upload-bulk`

**Request:** Multipart form with `files` (max 5, each max 20MB) and `access_level`

**Success Response (201):**
```json
{
  "message": "2 documents ingested successfully",
  "results": [
    {"source": "policy1.pdf", "chunks_created": 15, "status": "success"},
    {"source": "policy2.pdf", "chunks_created": 8, "status": "success"}
  ],
  "total_chunks": 23
}
```

### C. `GET /api/v1/documents`

**Success Response (200):**
```json
{
  "documents": [
    {
      "source": "remote_work_policy_2024.pdf",
      "chunk_count": 24,
      "access_level": "all",
      "ingested_at": "2026-07-01T10:00:00Z"
    }
  ],
  "total_documents": 1,
  "total_chunks": 24
}
```

### D. `GET /api/v1/documents/{source}`

**Success Response (200):**
```json
{
  "source": "remote_work_policy_2024.pdf",
  "access_level": "all",
  "chunks": [
    {
      "chunk_index": 0,
      "content": "Remote Work Policy\n\nSection 1: Overview...",
      "page": 1,
      "section": "Overview"
    }
  ],
  "total_chunks": 24
}
```

### E. `DELETE /api/v1/documents/{source}`

**Success Response (200):**
```json
{
  "message": "Document deleted successfully",
  "source": "remote_work_policy_2024.pdf",
  "chunks_deleted": 24
}
```

### F. `GET /api/v1/documents/stats`

**Success Response (200):**
```json
{
  "total_documents": 3,
  "total_chunks": 89,
  "total_characters": 52340,
  "access_level_distribution": {
    "all": 65,
    "manager": 15,
    "hr_admin": 9
  },
  "largest_document": "employee_handbook.pdf",
  "last_ingested": "2026-07-01T14:30:00Z"
}
```

---

## 5. Chunking Strategy

- **Chunk Size:** 1000 characters
- **Chunk Overlap:** 200 characters
- **Respect sentence boundaries** (no mid-sentence splits)
- **Minimum chunk size:** 100 characters (discard smaller)
- **Section detection:** Pattern matching for headings
- **Page tracking:** From `[PAGE X]` markers in parsed PDFs

---

## 6. New Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   │
│   ├── api/v1/
│   │   ├── __init__.py
│   │   └── documents.py          # 🔵 PRESENTATION — document endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── ingestion.py          # 🟢 BUSINESS LOGIC — ingestion pipeline
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py               # 🟡 Base repository with common CRUD
│   │   └── document.py           # 🟡 Document-specific queries
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── message.py
│   │   ├── feedback.py
│   │   └── document.py           # ⚪ HRDocument ORM model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   └── document.py           # 📋 Document request/response schemas
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py           # JWT + password hashing
│   │   ├── deps.py               # Dependency injection (get_db, get_current_user)
│   │   └── exceptions.py         # Custom exceptions
│   │
│   └── utils/
│       ├── __init__.py
│       ├── parser.py             # PDF/DOCX/TXT parsing
│       ├── chunker.py            # Text chunking logic
│       └── embedder.py           # Gemini embedding wrapper
```

---

## 7. Files to Create (Following Layered Architecture)

### Layer 1: Models (`app/models/`)

#### `app/models/document.py`

SQLAlchemy ORM model for `hr_documents` table:
- **`HRDocument`** class inheriting from `Base`
- `__tablename__ = "hr_documents"`
- Columns: id, content, embedding (Vector), source, page, section, chunk_index, access_level, created_at
- No relationships needed (standalone table)

---

### Layer 2: Schemas (`app/schemas/`)

#### `app/schemas/document.py`

Pydantic models:

- **`DocumentUploadResponse`**: message, source, chunks_created, total_chars, access_level
- **`BulkUploadResult`**: source, chunks_created, status
- **`BulkUploadResponse`**: message, results (list[BulkUploadResult]), total_chunks
- **`DocumentSummary`**: source, chunk_count, access_level, ingested_at
- **`DocumentListResponse`**: documents (list[DocumentSummary]), total_documents, total_chunks
- **`ChunkDetail`**: chunk_index, content, page, section
- **`DocumentDetailResponse`**: source, access_level, chunks (list[ChunkDetail]), total_chunks
- **`DocumentDeleteResponse`**: message, source, chunks_deleted
- **`AccessLevelDistribution`**: all (int), manager (int), hr_admin (int)
- **`DocumentStatsResponse`**: total_documents, total_chunks, total_characters, access_level_distribution, largest_document, last_ingested

---

### Layer 3: Repositories (`app/repositories/`)

#### `app/repositories/base.py`

Generic base repository:

- **`BaseRepository[ModelType]`** class
  - `__init__(self, db: AsyncSession)` — stores session
  - `get_by_id(self, id: UUID) -> Optional[ModelType]`
  - `get_all(self, skip=0, limit=100) -> list[ModelType]`
  - `add(self, instance: ModelType) -> ModelType`
  - `add_all(self, instances: list[ModelType]) -> list[ModelType]`
  - `delete(self, instance: ModelType) -> None`
  - `commit(self) -> None`
  - `rollback(self) -> None`

#### `app/repositories/document.py`

Document-specific repository:

- **`DocumentRepository(BaseRepository[HRDocument])`**
  - `async get_by_source(source: str) -> list[HRDocument]` — all chunks for a document
  - `async delete_by_source(source: str) -> int` — delete all chunks, return count
  - `async insert_chunks(chunks: list[dict]) -> list[HRDocument]` — bulk insert with embeddings
  - `async get_document_stats() -> dict` — aggregation query for stats
  - `async list_documents() -> list[dict]` — grouped by source with counts
  - `async source_exists(source: str) -> bool` — check if document already ingested

---

### Layer 4: Services (`app/services/`)

#### `app/services/ingestion.py`

Business logic — stateless, returns dicts, never HTTP responses:

- **`IngestionService`** class
  - `__init__(self, db: AsyncSession, gemini_api_key: str)`
  - `async ingest_document(file_bytes: bytes, filename: str, access_level: str = "all") -> dict`
    - Full pipeline: parse → detect sections → chunk → embed → store
    - Returns dict with success/error info
    - Checks for duplicate source and replaces
  - `async ingest_multiple(files: list[tuple[bytes, str]], access_level: str = "all") -> dict`
    - Processes multiple files sequentially
    - Returns aggregated results
  - `async delete_document(source: str) -> dict`
    - Deletes all chunks for source
    - Returns deletion count
  - `async get_document(source: str) -> dict`
    - Returns document with all chunks ordered by chunk_index
  - `async list_documents() -> dict`
    - Returns all documents with stats
  - `async get_stats() -> dict`
    - Returns ingestion statistics

---

### Layer 5: API Routes (`app/api/v1/`)

#### `app/api/v1/__init__.py`

- Empty file

#### `app/api/v1/documents.py`

FastAPI router — thin controllers, no business logic:

- **Router:** prefix="" (full path in main.py), tags=["Documents"]
- All endpoints protected by `get_current_admin_user` dependency
- Each endpoint:
  1. Validates request
  2. Creates `IngestionService` with db session
  3. Calls service method
  4. Returns HTTP response with appropriate status code

**Endpoints:**
- `POST /upload` — multipart file upload
- `POST /upload-bulk` — multiple file upload
- `GET /` — list documents
- `GET /{source}` — get document detail
- `DELETE /{source}` — delete document
- `GET /stats/` — ingestion statistics

---

### Layer 6: Utilities (`app/utils/`)

#### `app/utils/parser.py`

Pure functions for document parsing:

- `parse_pdf(file_bytes: bytes) -> str` — Extract text with page markers
- `parse_docx(file_bytes: bytes) -> str` — Extract text with section hints
- `parse_txt(file_bytes: bytes) -> str` — Decode with UTF-8 fallback
- `extract_text(file_bytes: bytes, filename: str) -> str` — Route to correct parser
- `detect_sections(text: str) -> list[dict]` — Identify section boundaries
- `validate_file_type(filename: str) -> bool` — Check extension is allowed
- `ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}`

#### `app/utils/chunker.py`

Pure functions for text chunking:

- `chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[dict]`
  - Returns list of `{"content": str, "chunk_index": int, "start_char": int, "end_char": int}`
- `assign_sections_to_chunks(chunks: list[dict], sections: list[dict]) -> list[dict]`
- `assign_page_to_chunks(chunks: list[dict], page_markers: list[dict]) -> list[dict]`

#### `app/utils/embedder.py`

Gemini embedding wrapper:

- `async embed_texts(texts: list[str], api_key: str, task_type: str = "retrieval_document") -> list[list[float]]`
  - Batches of 50
  - 3 retries with exponential backoff
  - Returns 768-dim vectors
- `async embed_single(text: str, api_key: str) -> list[float]`
  - Single text convenience wrapper

---

### Layer 7: Core (`app/core/`)

#### `app/core/deps.py`

Add new dependency:

- **`get_current_admin_user(current_user = Depends(get_current_user)) -> User`**
  - Checks `current_user.role == "hr_admin"`
  - Raises `403` if not admin
  - Returns user if admin

#### `app/core/exceptions.py`

Custom exceptions:

- **`IngestionError`** — Base ingestion exception
- **`UnsupportedFileTypeError`** — Wrong file extension
- **`FileTooLargeError`** — Exceeds max size
- **`EmptyDocumentError`** — No extractable text
- **`EmbeddingGenerationError`** — Gemini API failure
- **`DocumentNotFoundError`** — Source not found in DB

---

## 8. Changes to Existing Files

### A. `app/main.py`

```python
from app.api.v1 import documents
from app.core.deps import get_current_admin_user

app.include_router(
    documents.router,
    prefix="/api/v1/documents",
    tags=["Documents"]
)
```

### B. `app/config.py`

Add settings:
```python
MAX_FILE_SIZE_MB: int = 20
CHUNK_SIZE: int = 1000
CHUNK_OVERLAP: int = 200
EMBEDDING_MODEL: str = "gemini-embedding-001"
EMBEDDING_DIMENSIONS: int = 768
EMBEDDING_BATCH_SIZE: int = 50
ALLOWED_FILE_TYPES: list = ["pdf", "docx", "txt"]
```

### C. `app/models/__init__.py`

Import all models for Base metadata:
```python
from app.models.user import User
from app.models.session import Session
from app.models.message import Message
from app.models.feedback import Feedback
from app.models.document import HRDocument
```

---

## 9. Files to Create (Complete List)

```
backend/app/api/v1/__init__.py
backend/app/api/v1/documents.py
backend/app/services/__init__.py
backend/app/services/ingestion.py
backend/app/repositories/__init__.py
backend/app/repositories/base.py
backend/app/repositories/document.py
backend/app/models/document.py
backend/app/schemas/document.py
backend/app/core/deps.py          (update with get_current_admin_user)
backend/app/core/exceptions.py
backend/app/utils/__init__.py
backend/app/utils/parser.py
backend/app/utils/chunker.py
backend/app/utils/embedder.py
```

---

## 10. Files to Change

```
backend/app/main.py               (add documents router)
backend/app/config.py             (add ingestion settings)
backend/app/models/__init__.py    (import HRDocument)
```

---

## 11. Dependencies

All in `requirements.txt`:
- `PyPDF2` — PDF parsing
- `python-docx` — DOCX parsing
- `google-generativeai` — Gemini embeddings
- `asyncpg` — Vector operations
- `pgvector` — Python pgvector client

---

## 12. Rules for Implementation

- **Thin controllers**: Routes only parse request, call service, return response
- **No business logic in routes**: All logic in services
- **Services return dicts**: Never HTTP responses — framework-agnostic
- **Repositories handle all SQL**: No raw queries in services or routes
- **Utility functions are pure**: No database or framework dependencies
- **Embedding model fixed**: `gemini-embedding-001`, 768 dimensions
- **Access control**: Only `hr_admin` role can manage documents
- **Duplicate handling**: Uploading same filename replaces old chunks
- **Transaction safety**: Rollback all chunks if any part fails
- **File validation**: Extension + magic bytes check
- **Chunk minimum**: 100 characters (discard smaller)
- **Batch size**: 50 texts per Gemini embedding call
- **Retry logic**: 3 retries with exponential backoff (1s, 2s, 4s)

---

## 13. Expected Behavior

1. HR admin uploads PDF → text extracted → chunked → embedded → stored → returns success with chunk count
2. Duplicate source → old chunks deleted → new chunks stored
3. Invalid file type → 400 error
4. Non-admin user → 403 error
5. Gemini API failure → retries 3 times → returns 500 if all fail

---

## 14. Error Handling Expectations

| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| Unsupported file type | 400 | "Unsupported file type: .jpg. Allowed: pdf, docx, txt" |
| File too large | 400 | "File size exceeds maximum of 20MB" |
| Empty document | 400 | "Could not extract text from file" |
| Gemini API failure | 500 | "Embedding generation failed after 3 attempts" |
| Source not found (delete) | 404 | "Document not found: {source}" |
| Not authenticated | 401 | "Not authenticated" |
| Not admin | 403 | "Only HR admins can manage documents" |

---

## 15. Definition of Done

- [ ] PDF/DOCX/TXT files correctly parsed
- [ ] Text chunked with 1000 char size, 200 char overlap
- [ ] Section detection works for common heading patterns
- [ ] Page numbers tracked from PDF markers
- [ ] Gemini `gemini-embedding-001` embeddings generated (768-dim)
- [ ] Chunks stored in `hr_documents` with correct metadata
- [ ] Duplicate source upload replaces old chunks
- [ ] Only hr_admin can upload/delete
- [ ] Bulk upload works (max 5 files)
- [ ] All endpoints follow thin-controller pattern
- [ ] Services return dicts, not HTTP responses
- [ ] Repositories handle all database queries
- [ ] Utility functions are pure and stateless
- [ ] Transaction rollback on partial failure
- [ ] All 6 endpoints work correctly
- [ ] Error responses use custom exception classes

---