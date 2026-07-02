# Feature 5: Vector Search Service

## 1. Overview

Build the vector search service that takes a user query, generates its embedding using Gemini `text-embedding-001`, performs cosine similarity search against the `hr_documents` table using pgvector, and returns ranked results with confidence scoring and access control filtering.

This establishes the **retrieval foundation** — the R in RAG. Without this, the agent cannot find relevant HR knowledge to answer from.

---

## 2. Depends on

- **Feature 1: Project Setup & Docker Environment** — PostgreSQL + pgvector running
- **Feature 2: Database Schema & Migrations** — `hr_documents` table with vector index exists
- **Feature 4: Document Ingestion Pipeline** — documents must be ingested before search works

---

## 3. Routes

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/v1/search` | Yes (JWT) | Search HR documents by query text |
| `GET` | `/api/v1/search/health` | No | Check if vector search is operational |

---

## 4. Route Specifications

### A. `POST /api/v1/search`

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "query": "What is the remote work policy?",
  "top_k": 5,
  "access_levels": ["all", "manager"],
  "min_score": 0.5
}
```

**Request Validation:**
- `query`: Non-empty string, max 1000 characters
- `top_k`: Integer between 1 and 20 (default: 5)
- `access_levels`: Array of valid access levels. If not provided, auto-populated based on user's role:
  - `employee` → `["all"]`
  - `manager` → `["all", "manager"]`
  - `hr_admin` → `["all", "manager", "hr_admin"]`
- `min_score`: Float between 0.0 and 1.0 (default: 0.5)

**Success Response (200):**
```json
{
  "query": "What is the remote work policy?",
  "results": [
    {
      "chunk_id": "uuid-string",
      "content": "Employees may work remotely up to 2 days per week...",
      "source": "remote_work_policy_2024.pdf",
      "page": 2,
      "section": "Eligibility",
      "score": 0.92,
      "confidence": "high"
    },
    {
      "chunk_id": "uuid-string",
      "content": "Remote work must be scheduled at least 24 hours in advance...",
      "source": "remote_work_policy_2024.pdf",
      "page": 3,
      "section": "Scheduling",
      "score": 0.85,
      "confidence": "high"
    },
    {
      "chunk_id": "uuid-string",
      "content": "Core hours for remote work are 10 AM to 4 PM...",
      "source": "employee_handbook.pdf",
      "page": 15,
      "section": "Remote Work Guidelines",
      "score": 0.72,
      "confidence": "medium"
    }
  ],
  "total_found": 3,
  "search_time_ms": 45
}
```

**Error Responses:**
- `400` — Empty query or invalid parameters
- `401` — Not authenticated
- `500` — Embedding generation failed or database error

---

### B. `GET /api/v1/search/health`

**Success Response (200):**
```json
{
  "status": "healthy",
  "vector_index_exists": true,
  "total_documents_indexed": 89,
  "embedding_model": "gemini-embedding-001",
  "embedding_dimensions": 768
}
```

---

## 5. Confidence Scoring Logic

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    CONFIDENCE THRESHOLDS                                             │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                                                                              │    │
│  │   Cosine Score ≥ 0.75    →    HIGH CONFIDENCE                                │    │
│  │   • Strong semantic match                                                   │    │
│  │   • Use for direct answer generation                                        │    │
│  │   • Display sources prominently                                             │    │
│  │                                                                              │    │
│  │   Cosine Score 0.50 – 0.74 →  MEDIUM CONFIDENCE                              │    │
│  │   • Moderate semantic match                                                  │    │
│  │   • Generate answer with disclaimer:                                         │    │
│  │     "I found some related information but I'm not fully confident..."        │    │
│  │                                                                              │    │
│  │   Cosine Score < 0.50    →    LOW CONFIDENCE                                 │    │
│  │   • Weak or no semantic match                                                │    │
│  │   • Do NOT generate answer from this context                                 │    │
│  │   • Return: "I don't have information about that in my knowledge base"       │    │
│  │                                                                              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  Edge Cases:                                                                         │
│  • All results below min_score → Return empty results with "no_match" status        │
│  • Only medium confidence results → Still return, but mark overall confidence       │
│  • Mix of high and low → Return only those above min_score threshold                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Access Control Logic

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ACCESS CONTROL BY USER ROLE                                       │
│                                                                                      │
│  The search service receives a list of allowed access_levels based on the user's     │
│  role. This prevents employees from seeing documents marked for managers only.       │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  USER ROLE          │  CAN ACCESS                                            │    │
│  ├──────────────────────┼───────────────────────────────────────────────────────┤    │
│  │  employee            │  access_level = 'all'                                  │    │
│  ├──────────────────────┼───────────────────────────────────────────────────────┤    │
│  │  manager             │  access_level IN ('all', 'manager')                   │    │
│  ├──────────────────────┼───────────────────────────────────────────────────────┤    │
│  │  hr_admin            │  access_level IN ('all', 'manager', 'hr_admin')       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  SQL Filtering:                                                                      │
│  WHERE access_level = ANY($1)   -- $1 = ['all', 'manager']                           │
│                                                                                      │
│  This is enforced at the DATABASE level, not in application code.                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. New Folder Structure (This Feature Only)

```text
backend/app/
├── api/v1/
│   └── search.py                 # 🔵 PRESENTATION — search endpoints
├── services/
│   └── search.py                 # 🟢 BUSINESS LOGIC — search orchestration
├── repositories/
│   └── document.py               # 🟡 UPDATE — add search query method
└── schemas/
    └── search.py                 # 📋 Search request/response schemas
```

---

## 8. Files to Create

### Layer 1: Schemas (`app/schemas/`)

#### `app/schemas/search.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class SearchRequest(BaseModel):
    """Request schema for vector search."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The search query text"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return"
    )
    access_levels: Optional[List[str]] = Field(
        default=None,
        description="Access levels to include. Auto-populated from user role if not provided."
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold"
    )

    @validator('access_levels')
    def validate_access_levels(cls, v):
        if v is not None:
            valid = {'all', 'manager', 'hr_admin'}
            for level in v:
                if level not in valid:
                    raise ValueError(f"Invalid access level: {level}. Must be one of {valid}")
        return v


class SearchResult(BaseModel):
    """Individual search result."""
    chunk_id: UUID
    content: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    score: float
    confidence: str  # "high", "medium", or "low"


class SearchResponse(BaseModel):
    """Response schema for vector search."""
    query: str
    results: List[SearchResult]
    total_found: int
    search_time_ms: float
    overall_confidence: Optional[str] = None  # "high", "medium", "low", or "no_match"


class SearchHealthResponse(BaseModel):
    """Health check response for search service."""
    status: str
    vector_index_exists: bool
    total_documents_indexed: int
    embedding_model: str
    embedding_dimensions: int
```

---

### Layer 2: Repositories (`app/repositories/`)

#### UPDATE: `app/repositories/document.py`

Add search-specific methods to the existing `DocumentRepository`:

```python
async def search_similar(
    self,
    query_embedding: list[float],
    access_levels: list[str],
    top_k: int = 5,
    min_score: float = 0.5,
) -> list[dict]:
    """
    Perform cosine similarity search using pgvector.
    
    Args:
        query_embedding: 768-dim embedding vector
        access_levels: List of allowed access levels
        top_k: Number of results to return
        min_score: Minimum similarity score (0.0 to 1.0)
    
    Returns:
        List of dicts with: id, content, source, page, section, score
    """
    # Use raw SQL for pgvector cosine similarity operator (<=>)
    # 1 - (embedding <=> query) converts cosine distance to cosine similarity
```

**SQL Query (parameterized):**

```sql
SELECT 
    id,
    content,
    source,
    page,
    section,
    1 - (embedding <=> $1::vector) AS score
FROM hr_documents
WHERE 
    access_level = ANY($2::text[])
    AND 1 - (embedding <=> $1::vector) >= $3
ORDER BY embedding <=> $1
LIMIT $4
```

Parameters:
- `$1`: query embedding as vector (list of 768 floats cast to pgvector)
- `$2`: array of allowed access levels (e.g., `['all', 'manager']`)
- `$3`: minimum score threshold
- `$4`: top_k limit

**Additional method:**

```python
async def get_total_indexed_count(self) -> int:
    """Get total number of indexed document chunks."""
    # SELECT COUNT(*) FROM hr_documents

async def check_vector_index_exists(self) -> bool:
    """Check if the ivfflat index exists on hr_documents."""
    # SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_hr_documents_embedding')
```

---

### Layer 3: Services (`app/services/`)

#### `app/services/search.py`

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.document import DocumentRepository
from app.utils.embedder import embed_single
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
import time


class SearchService:
    """
    Stateless service orchestrating vector search.
    Returns dicts, never HTTP responses.
    """
    
    def __init__(self, db: AsyncSession, gemini_api_key: str):
        self.db = db
        self.gemini_api_key = gemini_api_key
        self.document_repo = DocumentRepository(db)
    
    async def search(
        self,
        query: str,
        user_role: str,
        top_k: int = 5,
        access_levels: Optional[list[str]] = None,
        min_score: float = 0.5,
    ) -> dict:
        """
        Full search pipeline:
        1. Determine access levels from user role (if not provided)
        2. Generate query embedding
        3. Perform similarity search
        4. Assign confidence levels
        5. Return ranked results
        """
        start_time = time.time()
        
        # Step 1: Determine access levels
        if access_levels is None:
            access_levels = self._get_access_levels_for_role(user_role)
        
        # Step 2: Generate query embedding
        query_embedding = await embed_single(
            text=query,
            api_key=self.gemini_api_key,
            task_type="RETRIEVAL_QUERY"
        )
        
        # Step 3: Search
        results = await self.document_repo.search_similar(
            query_embedding=query_embedding,
            access_levels=access_levels,
            top_k=top_k,
            min_score=min_score,
        )
        
        # Step 4: Assign confidence
        results = self._assign_confidence(results)
        
        # Step 5: Build response
        elapsed_ms = (time.time() - start_time) * 1000
        
        overall_confidence = self._calculate_overall_confidence(results)
        
        return {
            "query": query,
            "results": results,
            "total_found": len(results),
            "search_time_ms": round(elapsed_ms, 2),
            "overall_confidence": overall_confidence,
        }
    
    async def health_check(self) -> dict:
        """Check search service health."""
        index_exists = await self.document_repo.check_vector_index_exists()
        total_docs = await self.document_repo.get_total_indexed_count()
        
        return {
            "status": "healthy" if index_exists and total_docs > 0 else "degraded",
            "vector_index_exists": index_exists,
            "total_documents_indexed": total_docs,
            "embedding_model": "gemini-embedding-001",
            "embedding_dimensions": 768,
        }
    
    def _get_access_levels_for_role(self, role: str) -> list[str]:
        """Map user role to allowed access levels."""
        role_access_map = {
            "employee": ["all"],
            "manager": ["all", "manager"],
            "hr_admin": ["all", "manager", "hr_admin"],
        }
        return role_access_map.get(role, ["all"])
    
    def _assign_confidence(self, results: list[dict]) -> list[dict]:
        """Assign confidence level based on similarity score."""
        for result in results:
            score = result["score"]
            if score >= 0.75:
                result["confidence"] = "high"
            elif score >= 0.50:
                result["confidence"] = "medium"
            else:
                result["confidence"] = "low"
        return results
    
    def _calculate_overall_confidence(self, results: list[dict]) -> str:
        """Calculate overall search confidence."""
        if not results:
            return "no_match"
        
        scores = [r["score"] for r in results]
        avg_score = sum(scores) / len(scores)
        
        if avg_score >= 0.75:
            return "high"
        elif avg_score >= 0.50:
            return "medium"
        else:
            return "low"
```

---

### Layer 4: API Routes (`app/api/v1/`)

#### `app/api/v1/search.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.search import SearchService
from app.schemas.search import SearchRequest, SearchResponse, SearchHealthResponse
from app.config import settings

router = APIRouter()


@router.post("/", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search HR documents using semantic similarity.
    
    The search generates an embedding for the query text,
    then finds the most similar document chunks using pgvector
    cosine similarity, filtered by the user's access level.
    """
    try:
        service = SearchService(db, settings.GEMINI_API_KEY)
        result = await service.search(
            query=request.query,
            user_role=current_user.role,
            top_k=request.top_k,
            access_levels=request.access_levels,
            min_score=request.min_score,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/health", response_model=SearchHealthResponse)
async def search_health(db: AsyncSession = Depends(get_db)):
    """
    Check if the vector search service is operational.
    Public endpoint — no authentication required.
    """
    service = SearchService(db, settings.GEMINI_API_KEY)
    return await service.health_check()
```

---

## 9. Changes to Existing Files

### A. `backend/app/main.py`

```python
from app.api.v1 import search

app.include_router(
    search.router,
    prefix="/api/v1/search",
    tags=["Search"]
)
```

### B. `backend/app/repositories/document.py`

Add the three search methods from section 8 (Layer 2) to the existing `DocumentRepository` class.

---

## 10. Files to Create

```
backend/app/schemas/search.py
backend/app/services/search.py
backend/app/api/v1/search.py
```

---

## 11. Files to Change

```
backend/app/main.py                     (add search router)
backend/app/repositories/document.py    (add search methods)
```

---

## 12. Dependencies

All already in `requirements.txt`:
- `google-genai>=1.0.0` — Gemini embeddings (updated SDK)
- `asyncpg` — Direct database access for vector operations
- `pgvector` — Python pgvector client

---

## 13. Rules for Implementation

- **pgvector cosine distance operator `<=>`**: Returns cosine distance (0 to 2). Convert to similarity: `1 - (embedding <=> query)` gives 1.0 (identical) to -1.0 (opposite)
- **Always filter by access_level**: Never return chunks the user shouldn't see
- **Use parameterized queries only**: `$1::vector`, `$2::text[]` — never string formatting
- **Embedding model fixed**: `gemini-embedding-001` with `output_dimensionality=768`
- **Task type for queries**: `RETRIEVAL_QUERY` (not `RETRIEVAL_DOCUMENT` — that's for ingestion)
- **Query embedding is sync**: Wrap in `asyncio.to_thread()` for async FastAPI
- **Confidence thresholds are configurable but have sensible defaults** (high ≥0.75, medium ≥0.50)
- **Results must be ordered by similarity score descending**
- **Service returns dicts, not ORM objects or HTTP responses**
- **Thin controller**: Route only parses request, calls service, returns response

---

## 14. pgvector Query Details

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    PGVECTOR QUERY REFERENCE                                           │
│                                                                                      │
│  Cosine Distance Operator: <=>                                                         │
│  • Returns: 0 (identical vectors) to 2 (opposite vectors)                            │
│  • Conversion to similarity: similarity = 1 - distance                              │
│  • Range after conversion: 1.0 (identical) to -1.0 (opposite)                       │
│                                                                                      │
│  Parameterized Query:                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  query = """                                                                │    │
│  │      SELECT                                                                  │    │
│  │          id,                                                                 │    │
│  │          content,                                                            │    │
│  │          source,                                                             │    │
│  │          page,                                                               │    │
│  │          section,                                                            │    │
│  │          1 - (embedding <=> $1::vector) AS score                             │    │
│  │      FROM hr_documents                                                       │    │
│  │      WHERE                                                                   │    │
│  │          access_level = ANY($2::text[])                                      │    │
│  │          AND 1 - (embedding <=> $1::vector) >= $3                           │    │
│  │      ORDER BY embedding <=> $1                                               │    │
│  │      LIMIT $4                                                                │    │
│  │  """                                                                         │    │
│  │                                                                              │    │
│  │  # Execute with asyncpg connection                                           │    │
│  │  rows = await conn.fetch(query, embedding, access_levels, min_score, top_k) │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  Vector Index:                                                                       │
│  • ivfflat index created in Feature 2                                                │
│  • pgvector automatically uses the index for ORDER BY with <=>                       │
│  • Index requires at least ~50 rows to be effective                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Expected Behavior

### Successful search:
1. Authenticated user sends query: "What is remote work policy?"
2. Query is embedded using `RETRIEVAL_QUERY` task type
3. pgvector performs cosine similarity search filtered by user's access level
4. Results returned sorted by score, with confidence labels
5. Response includes search time for observability

### No results:
1. Query returns all results below `min_score`
2. Response: `{"results": [], "total_found": 0, "overall_confidence": "no_match"}`

### Access control:
1. Employee searches for "executive compensation"
2. Chunks exist but with `access_level = "hr_admin"`
3. Employee's access levels are `["all"]` only
4. Those chunks are filtered out at the database level
5. Employee sees no results (or unrelated low-score results)

### Empty database:
1. No documents ingested yet
2. Search returns empty results
3. Health endpoint shows `total_documents_indexed: 0`, status `"degraded"`

---

## 16. Error Handling Expectations

| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| Empty query string | 400 | "Query must not be empty" |
| Query exceeds 1000 chars | 400 | "Query must be 1000 characters or less" |
| Invalid access_level value | 400 | "Invalid access level: xyz" |
| top_k out of range | 400 | "top_k must be between 1 and 20" |
| min_score out of range | 400 | "min_score must be between 0.0 and 1.0" |
| Gemini embedding fails | 500 | "Failed to generate query embedding" |
| Database connection error | 500 | "Search service temporarily unavailable" |
| Not authenticated | 401 | "Not authenticated" |

---

## 17. Verification Steps

```bash
# 1. Health check (no auth needed)
curl http://localhost:8000/api/v1/search/health

# 2. Search with valid token (requires Feature 3 login first)
# First login to get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@company.com","password":"john123"}' \
  | jq -r '.access_token')

# 3. Search as employee (only sees "all" access documents)
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "What is the remote work policy?",
    "top_k": 3
  }'

# 4. Search as admin (sees all documents)
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"admin123"}' \
  | jq -r '.access_token')

curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "query": "executive compensation",
    "top_k": 5,
    "min_score": 0.3
  }'

# 5. Search with custom access levels (overrides role-based)
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "leave policy",
    "top_k": 5,
    "access_levels": ["all", "manager"]
  }'
```

---

## 18. Definition of Done

- [ ] `POST /api/v1/search` returns ranked results with scores and confidence
- [ ] Query embedding uses `gemini-embedding-001` with `RETRIEVAL_QUERY` task type
- [ ] `output_dimensionality=768` is explicitly set
- [ ] Results filtered by user role's access levels automatically
- [ ] Custom `access_levels` parameter overrides role-based filtering
- [ ] Confidence levels correctly assigned (high ≥0.75, medium ≥0.50, low <0.50)
- [ ] `min_score` parameter works correctly
- [ ] Results sorted by similarity score descending
- [ ] Search time is tracked and returned in response
- [ ] Health endpoint works without authentication
- [ ] Health endpoint reports accurate document count
- [ ] Empty query returns 400 error
- [ ] Invalid parameters return 400 errors
- [ ] No results returns empty array with `"overall_confidence": "no_match"`
- [ ] Access control enforced at database level (SQL WHERE clause)
- [ ] Service returns dicts (not ORM objects or HTTP responses)
- [ ] Route is a thin controller (no business logic)
- [ ] All SQL uses parameterized queries
- [ ] Works with new `google-genai` SDK (synchronous, wrapped in `asyncio.to_thread`)
- [ ] Search works after Feature 4 documents are ingested