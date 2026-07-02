# Feature 8: RAG Pipeline (Core Q&A) — Complete Specification

## 1. Overview

Build the complete Retrieval-Augmented Generation pipeline that combines all previous features into a working HR Q&A agent. This is the **core feature** — the `/query` endpoint that takes a user's question, classifies it, retrieves relevant documents, builds a prompt with context and conversation history, streams the AI-generated answer, and returns it with source citations.

After this feature, the agent can actually answer HR questions end-to-end.

---

## 2. Depends on

- **Feature 1: Project Setup & Docker Environment** — all services running
- **Feature 2: Database Schema & Migrations** — all tables exist with indexes
- **Feature 3: User Authentication** — JWT auth working, user context available
- **Feature 4: Document Ingestion Pipeline** — HR documents indexed with embeddings
- **Feature 5: Vector Search Service** — semantic search operational
- **Feature 6: Gemini Service Layer** — unified AI service with all methods
- **Feature 7: Query Classifier** — message classification and routing logic

---

## 3. Routes

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/v1/query` | Yes (JWT) | Main Q&A endpoint (streaming SSE) |
| `POST` | `/api/v1/query/test` | Yes (JWT) | Test endpoint (non-streaming JSON) |
| `GET` | `/api/v1/query/health` | No | Query pipeline health check |

---

## 4. Route Specifications

### A. `POST /api/v1/query` (Streaming)

**Headers:**
- `Authorization: Bearer <access_token>`
- `Accept: text/event-stream`

**Request Body:**
```json
{
  "query": "What is the remote work policy and can I combine it with leave?",
  "session_id": null
}
```

**Request Validation:**
- `query`: Non-empty string, max 2000 characters
- `session_id`: Optional UUID string. If null, new session created. If provided, must belong to authenticated user.

**Response:** Server-Sent Events (SSE) stream

```
event: token
data: {"token": "Based"}

event: token
data: {"token": " on"}

event: token
data: {"token": " our"}

event: token
data: {"token": " remote"}

event: token
data: {"token": " work"}

event: token
data: {"token": " policy"}

event: token
data: {"token": ","}

event: token
data: {"token": " employees"}

... (continues for all tokens) ...

event: sources
data: {"sources": [{"document": "Remote Work Policy 2024", "page": 3, "section": "Eligibility", "excerpt": "Employees may work remotely up to 2 days per week with manager approval..."}, {"document": "Leave Policy 2024", "page": 2, "section": "Leave Combination", "excerpt": "Annual leave may be combined with remote work days subject to manager approval..."}]}

event: done
data: {"message_id": "550e8400-e29b-41d4-a716-446655440000", "session_id": "660e8400-e29b-41d4-a716-446655440001", "confidence": "high", "tokens_used": 156, "processing_time_ms": 850}
```

**SSE Event Specifications:**

| Event Name | Data Payload | When Sent |
|-----------|-------------|-----------|
| `token` | `{"token": "string"}` | For each token generated (may merge small tokens) |
| `sources` | `{"sources": [SourceObject]}` | After final token, before done event |
| `done` | `{"message_id": "uuid", "session_id": "uuid", "confidence": "string", "tokens_used": int, "processing_time_ms": float}` | Final event, stream complete |
| `error` | `{"error": "string", "detail": "string", "error_type": "string"}` | On any failure during processing |

**SourceObject Format:**
```json
{
  "document": "Remote Work Policy 2024",
  "page": 3,
  "section": "Eligibility",
  "excerpt": "Employees may work remotely up to 2 days per week..."
}
```

**Error SSE Event Example:**
```
event: error
data: {"error": "Search service unavailable", "detail": "Vector search failed after 3 retries", "error_type": "retrieval_failed"}
```

---

### B. `POST /api/v1/query/test` (Non-streaming)

**Request Body:** Same as `/api/v1/query`

**Success Response (200):**
```json
{
  "query": "What is the remote work policy?",
  "rewritten_query": null,
  "classification": "hr_question",
  "classification_confidence": 0.95,
  "retrieved_chunks": [
    {
      "chunk_id": "uuid",
      "content": "Employees may work remotely up to 2 days per week...",
      "source": "remote_work_policy_2024.pdf",
      "page": 3,
      "section": "Eligibility",
      "score": 0.92,
      "confidence": "high"
    }
  ],
  "retrieval_count": 3,
  "overall_confidence": "high",
  "answer": "Based on our remote work policy, employees may work remotely up to 2 days per week with manager approval...",
  "sources": [
    {
      "document": "Remote Work Policy 2024",
      "page": 3,
      "section": "Eligibility",
      "excerpt": "Employees may work remotely..."
    }
  ],
  "tokens_used": 245,
  "processing_time_ms": 1200,
  "pipeline_steps": {
    "classification_ms": 150,
    "rewriting_ms": null,
    "retrieval_ms": 45,
    "generation_ms": 980,
    "storage_ms": 25
  }
}
```

**Response Fields:**
- `rewritten_query`: null for non-follow-ups, contains rewritten query for follow-ups
- `classification_confidence`: Confidence from classifier
- `retrieval_count`: Number of chunks retrieved above threshold
- `pipeline_steps`: Timing breakdown for debugging/optimization

---

### C. `GET /api/v1/query/health`

**Success Response (200):**
```json
{
  "status": "healthy",
  "components": {
    "classifier": "available",
    "search": "available",
    "gemini": "available",
    "database": "connected"
  },
  "documents_indexed": 89,
  "active_sessions": 12
}
```

---

## 5. RAG Pipeline — Complete Flow

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE — END TO END FLOW                                     │
│                                                                                      │
│  USER QUERY: "What is remote work policy?"                                           │
│       │                                                                              │
│       ▼                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 0: VALIDATE & LOAD CONTEXT                                             │    │
│  │  • Validate request body (query not empty, session_id valid if provided)     │    │
│  │  • Load user from JWT token                                                  │    │
│  │  • Load or create session (for session management — Feature 9)               │    │
│  │  • Load conversation history (last 6 messages from this session)             │    │
│  └───────────────────────────────────────┬─────────────────────────────────────┘    │
│                                          │                                           │
│                                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: CLASSIFY                                                            │    │
│  │  Input: user_message, conversation_history                                    │    │
│  │  Service: ClassifierService.classify()                                        │    │
│  │  Model: gemini-2.5-flash (temp=0.1, max_tokens=50)                           │    │
│  │  Output: classification, confidence, action, requires_retrieval,             │    │
│  │          requires_rewriting, direct_response (if applicable)                   │    │
│  └───────────────────────────────────────┬─────────────────────────────────────┘    │
│                                          │                                           │
│                     ┌────────────────────┼────────────────────┐                      │
│                     │                    │                    │                      │
│                     ▼                    ▼                    ▼                      │
│              ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│              │ GREETING /   │    │ FOLLOW_UP    │    │ HR_QUESTION  │               │
│              │ BOT_Q / OOD  │    │              │    │              │               │
│              │              │    │              │    │              │               │
│              │ Return       │    │ Go to        │    │ Go to        │               │
│              │ direct       │    │ Step 1.5     │    │ Step 2       │               │
│              │ response     │    │              │    │              │               │
│              │ (no LLM)     │    │              │    │              │               │
│              └──────┬───────┘    └──────┬───────┘    └──────┬───────┘               │
│                     │                   │                   │                        │
│                     ▼                   ▼                   │                        │
│              ┌──────────────┐    ┌──────────────┐           │                        │
│              │ STEP 6:      │    │ STEP 1.5:    │           │                        │
│              │ RESPOND      │    │ REWRITE      │           │                        │
│              │ DIRECTLY     │    │ QUERY        │           │                        │
│              │              │    │              │           │                        │
│              │ Return       │    │ Rewrite      │           │                        │
│              │ template     │    │ follow-up    │           │                        │
│              │ response     │    │ → standalone │           │                        │
│              │              │    │ question     │           │                        │
│              └──────────────┘    └──────┬───────┘           │                        │
│                                         │                   │                        │
│                                         └─────────┬─────────┘                        │
│                                                   ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 2: RETRIEVE                                                            │    │
│  │  Input: query (original or rewritten), user_role                              │    │
│  │  Service: SearchService.search()                                              │    │
│  │  Model: gemini-embedding-001 (RETRIEVAL_QUERY, dims=768)                      │    │
│  │  • Generate query embedding                                                   │    │
│  │  • Cosine similarity search in pgvector                                       │    │
│  │  • Filter by access_level based on user role                                  │    │
│  │  • Filter by min_score (0.5)                                                  │    │
│  │  • Return top_k=5 results with scores                                         │    │
│  │  Output: list of chunks (id, content, source, page, section, score)          │    │
│  └───────────────────────────────────────┬─────────────────────────────────────┘    │
│                                          │                                           │
│                                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 3: CONFIDENCE GATE                                                     │    │
│  │  Check highest score from retrieval:                                          │    │
│  │                                                                               │    │
│  │  ┌─────────────────────────────────────────────────────────────────────┐      │    │
│  │  │ TOP SCORE ≥ 0.75 → HIGH CONFIDENCE                                    │      │    │
│  │  │ → Proceed to Step 4 (generate full answer)                            │      │    │
│  │  │ → No disclaimer needed                                                │      │    │
│  │  ├─────────────────────────────────────────────────────────────────────┤      │    │
│  │  │ TOP SCORE 0.50-0.74 → MEDIUM CONFIDENCE                               │      │    │
│  │  │ → Proceed to Step 4 (generate with disclaimer)                        │      │    │
│  │  │ → Add to prompt: "Note: I'm not fully confident in this response.     │      │    │
│  │  │    Please verify with HR if needed."                                   │      │    │
│  │  ├─────────────────────────────────────────────────────────────────────┤      │    │
│  │  │ TOP SCORE 0.30-0.49 → LOW CONFIDENCE                                  │      │    │
│  │  │ → Return soft fallback response (no generation)                       │      │    │
│  │  │ → "I found some related information but couldn't find a clear         │      │    │
│  │  │    answer. Try rephrasing or contact HR."                              │      │    │
│  │  ├─────────────────────────────────────────────────────────────────────┤      │    │
│  │  │ TOP SCORE < 0.30 OR NO RESULTS → NO MATCH                             │      │    │
│  │  │ → Return hard fallback response (no generation)                       │      │    │
│  │  │ → "I don't have information about that in my knowledge base."         │      │    │
│  │  └─────────────────────────────────────────────────────────────────────┘      │    │
│  └───────────────────────────────────────┬─────────────────────────────────────┘    │
│                                          │                                           │
│                              ┌───────────┴───────────┐                               │
│                              │                       │                               │
│                         HIGH/MEDIUM            LOW/NO MATCH                          │
│                              │                       │                               │
│                              ▼                       ▼                               │
│  ┌─────────────────────────────────────┐  ┌──────────────────────────────┐          │
│  │  STEP 4: BUILD PROMPT               │  │  STEP 6: RETURN FALLBACK     │          │
│  │                                     │  │  RESPONSE                    │          │
│  │  Assembles:                         │  │                              │          │
│  │  • System prompt (rules)            │  │  Pre-defined fallback text   │          │
│  │  • Conversation history             │  │  based on confidence tier    │          │
│  │  • Retrieved context with sources   │  │                              │          │
│  │  • User query                       │  │  → Store message             │          │
│  │  • Confidence disclaimer (if med)   │  │  → Return response           │          │
│  └──────────────────┬──────────────────┘  └──────────────────────────────┘          │
│                     │                                                                │
│                     ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 5: GENERATE (STREAMING)                                                │    │
│  │  Service: GeminiService.generate_stream()                                     │    │
│  │  Model: gemini-2.5-flash                                                      │    │
│  │  Config: temperature=0.3, max_output_tokens=1024, top_p=0.95                  │    │
│  │  • Send prompt to Gemini                                                      │    │
│  │  • Stream tokens back one at a time                                           │    │
│  │  • Yield SSE token events                                                     │    │
│  │  • After streaming: extract sources from retrieved chunks                    │    │
│  │  • Yield SSE sources event                                                    │    │
│  │  • Yield SSE done event with metadata                                         │    │
│  └───────────────────────────────────────┬─────────────────────────────────────┘    │
│                                          │                                           │
│                                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 6: STORE & RESPOND                                                     │    │
│  │  • Store user message in messages table                                       │    │
│  │  • Store assistant response in messages table                                 │    │
│  │  • Update session last_active timestamp                                       │    │
│  │  • Log interaction (query, classification, confidence, tokens, time)         │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Prompt Templates

### A. System Prompt for Answer Generation

```
You are an HR assistant for [Company Name]. Your job is to answer employee questions accurately using ONLY the provided context from official company documents.

RULES:
1. Answer ONLY using the information in the CONTEXT section below. Do not use outside knowledge or make assumptions.
2. If the CONTEXT doesn't contain enough information to answer fully, say so clearly: "I don't have complete information about that in my knowledge base. You may want to contact HR directly."
3. Always cite your sources in your answer using this format: [Source: Document Name, Page X, Section Y]
4. Be concise but complete. Use bullet points for lists and clear paragraph breaks for readability.
5. Never make up policy details, numbers, dates, or eligibility criteria not explicitly present in the context.
6. If the user asks about their personal data (leave balance, salary, personal schedule, etc.), explain: "I can only provide general policy information. For your personal records, please check the HR portal or contact HR directly."
7. Maintain a professional, friendly, and helpful tone.
8. If the confidence is MEDIUM, include this disclaimer at the end: "⚠️ Please verify this information with HR as I'm not fully confident in this response."
9. Format your answer for readability:
   - Use bullet points for lists
   - Use numbered steps for processes
   - Use paragraphs for explanations
   - Keep paragraphs short (2-3 sentences)
10. If the question is ambiguous, ask for clarification rather than guessing.
```

### B. User Prompt Template

```
CONVERSATION HISTORY:
{conversation_history}

CONTEXT FROM OFFICIAL DOCUMENTS:
---
{retrieved_context}
---

USER QUESTION: {user_query}

{confidence_note}

ASSISTANT RESPONSE:
```

### C. Retrieved Context Format

Each chunk formatted as:
```
[Source: {source}, Page {page}, Section: {section}]
{content}
---
```

### D. Conversation History Format

```
User: {message_content}
Assistant: {message_content}
User: {message_content}
Assistant: {message_content}
```

Empty history:
```
No previous conversation.
```

### E. Confidence Note (only for MEDIUM confidence)

```
Note: I'm not fully confident in the retrieved information for this question. Include a disclaimer in your response.
```

---

## 7. Query Rewriting Prompt (for Follow-ups)

```
Given the conversation history, rewrite the user's follow-up question into a complete, standalone question that includes all necessary context from the conversation. Do not answer the question — just rewrite it so it can be understood without the conversation history.

CONVERSATION:
{conversation_history}

FOLLOW-UP: {follow_up_message}

STANDALONE QUESTION:
```

**Rewrite Examples:**
- "explain that more" + history about remote work → "Explain the remote work policy in more detail"
- "what about the second point" + history listing 3 points → "What is the second point about [topic from history]?"
- "how do I apply" + history about leave → "How do I apply for leave according to the leave policy?"
- "and for contractors?" + history about full-time benefits → "What is the policy for contractors regarding [benefits topic]?"

---

## 8. "I Don't Know" / Fallback Responses

### Hard Fallback (No results or score < 0.30):
```
"I don't have information about that in my knowledge base. 

I can help you with questions about:
• Leave policies (annual leave, sick leave, parental leave)
• Remote work guidelines
• Benefits and insurance
• Payroll and compensation
• Company policies and procedures
• Onboarding and offboarding

Is there one of these topics I can help you with? Or you can contact HR directly for assistance with your specific question."
```

### Soft Fallback (Score 0.30 - 0.49):
```
"I found some related information in my knowledge base, but I couldn't find a clear answer to your specific question. 

Here's what might be related:
{list top 1-2 chunk excerpts if available}

I'd suggest:
• Trying to rephrase your question
• Asking about a specific policy or topic
• Contacting HR directly for personalized assistance

Is there another way I can help you?"
```

### Low Confidence Disclaimer (Score 0.50 - 0.74):
Added to the generated answer:
```
"⚠️ Please verify this information with HR as I'm not fully confident in this response."
```

---

## 9. Direct Responses (Non-Retrieval Classifications)

### Greeting Only:
```
"Hello {user_name}! I'm your HR assistant. I can help you with questions about:
• Company policies and procedures
• Leave and time-off policies
• Benefits and insurance
• Remote work guidelines
• Payroll and compensation

What would you like to know?"
```

### Bot Question:
```
"I'm an AI-powered HR assistant designed to help employees find information about company policies, benefits, leave, and other work-related topics. 

I work by searching through the company's official documents to find accurate answers to your questions. I can't access your personal employee records, but I can explain policies and procedures.

How can I help you today?"
```

### Out of Domain:
```
"I'm designed specifically to help with HR-related questions. I can assist you with topics like:

• Leave policies and time-off requests
• Benefits and insurance coverage
• Remote work guidelines
• Payroll, compensation, and reimbursements
• Company policies and employee handbook

Is there an HR topic I can help you with? If you have a non-HR question, I'd recommend reaching out to the appropriate department."
```

---

## 10. New Folder Structure

```
backend/app/
├── api/v1/
│   └── query.py                 # Query endpoints (streaming + test + health)
├── services/
│   └── rag.py                   # RAG pipeline orchestration
├── prompts/
│   └── rag.py                   # All prompt templates for RAG
├── schemas/
│   └── query.py                 # Query request/response schemas
```

---

## 11. Files to Create

### `app/prompts/rag.py`
- `SYSTEM_PROMPT` — constant string
- `USER_PROMPT_TEMPLATE` — with {conversation_history}, {retrieved_context}, {user_query}, {confidence_note}
- `REWRITE_SYSTEM_PROMPT` — for query rewriting
- `REWRITE_USER_PROMPT` — with {conversation_history}, {follow_up_message}
- `HARD_FALLBACK_RESPONSE` — when no results
- `SOFT_FALLBACK_RESPONSE` — when low confidence (with {related_excerpts})
- `GREETING_RESPONSE` — with {user_name}
- `BOT_QUESTION_RESPONSE` — static
- `OUT_OF_DOMAIN_RESPONSE` — static
- `LOW_CONFIDENCE_DISCLAIMER` — static disclaimer text

### `app/schemas/query.py`
- `QueryRequest` — query (str, min_length=1, max_length=2000), session_id (Optional[UUID])
- `QueryTestResponse` — query, rewritten_query, classification, classification_confidence, retrieved_chunks, retrieval_count, overall_confidence, answer, sources, tokens_used, processing_time_ms, pipeline_steps
- `RetrievedChunkDetail` — chunk_id, content, source, page, section, score, confidence
- `SourceDetail` — document, page, section, excerpt
- `PipelineSteps` — classification_ms, rewriting_ms, retrieval_ms, generation_ms, storage_ms
- `SSETokenEvent` — token: str
- `SSESourcesEvent` — sources: list[SourceDetail]
- `SSEDoneEvent` — message_id, session_id, confidence, tokens_used, processing_time_ms
- `SSEErrorEvent` — error, detail, error_type
- `QueryHealthResponse` — status, components (classifier, search, gemini, database), documents_indexed, active_sessions

### `app/services/rag.py`
- `RAGService` class
  - `__init__(db, gemini_service, config)` — stores dependencies
  - `process_query(query, user, session_id) -> AsyncIterator[str]` — main streaming pipeline
  - `process_query_test(query, user, session_id) -> dict` — non-streaming for debugging
  - `health_check() -> dict` — component health status
  - `_classify_message(message, history) -> dict` — step 1
  - `_rewrite_query(follow_up, history) -> str` — step 1.5
  - `_retrieve_context(query, user_role) -> dict` — step 2
  - `_apply_confidence_gate(search_results) -> tuple[str, dict]` — step 3
  - `_build_prompt(query, context, history, confidence) -> str` — step 4
  - `_format_context_for_prompt(chunks) -> str` — helper
  - `_format_history_for_prompt(messages) -> str` — helper
  - `_get_fallback_response(confidence_tier, chunks) -> str` — fallback responses
  - `_get_direct_response(classification, user_name) -> str` — direct responses
  - `_store_messages(user_id, session_id, query, response, sources, confidence, classification, tokens) -> dict` — step 6
  - `_build_sources_from_chunks(chunks) -> list[SourceDetail]` — source extraction

### `app/api/v1/query.py`
- Router with prefix="" (full path in main.py), tags=["Query"]
- `POST /` — streaming endpoint (SSE)
- `POST /test` — non-streaming debug endpoint
- `GET /health` — health check endpoint
- All endpoints protected by `get_current_user` dependency

---

## 12. Files to Change

### `app/main.py`
```python
from app.api.v1 import query

app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
```

### `app/config.py`
Add query pipeline settings:
```python
# RAG Pipeline Settings
TOP_K_RETRIEVAL: int = 5
MIN_RETRIEVAL_SCORE: float = 0.5
HIGH_CONFIDENCE_THRESHOLD: float = 0.75
MEDIUM_CONFIDENCE_THRESHOLD: float = 0.50
LOW_CONFIDENCE_THRESHOLD: float = 0.30
MAX_CONVERSATION_HISTORY: int = 6
MAX_COMPLETION_TOKENS: int = 1024
RESPONSE_TEMPERATURE: float = 0.3
STREAMING_CHUNK_DELAY_MS: int = 10
```

---

## 13. Dependencies

### Add to `requirements.txt`:
```
sse-starlette==2.1.3
```

---

## 14. RAGService Method Details

### `process_query(query, user, session_id) -> AsyncIterator[str]`

**Parameters:**
- `query: str` — user's raw message
- `user: User` — authenticated user ORM object
- `session_id: Optional[UUID]` — existing session or None

**Returns:** AsyncIterator yielding formatted SSE event strings

**Processing Steps:**
1. Record start time
2. Load/create session, load conversation history
3. Classify message via `ClassifierService`
4. Route based on classification:
   - Non-retrieval → yield direct response as token events → store → yield sources (empty) → yield done
   - Follow-up → rewrite query → go to step 5
   - HR question → go to step 5
5. Retrieve context via `SearchService`
6. Apply confidence gate:
   - HIGH/MEDIUM → build prompt → generate stream → yield tokens → yield sources → yield done
   - LOW/NO MATCH → yield fallback response as tokens → yield done
7. Store messages in database
8. On error: yield error event, log full traceback

### `_build_prompt(query, context_chunks, conversation_history, confidence) -> str`

**Parameters:**
- `query: str` — the question to answer
- `context_chunks: list[dict]` — retrieved chunks with metadata
- `conversation_history: list[dict]` — past messages
- `confidence: str` — "high" or "medium"

**Process:**
1. Format context using `_format_context_for_prompt()`
2. Format history using `_format_history_for_prompt()`
3. Determine confidence note (empty for high, disclaimer for medium)
4. Insert all into USER_PROMPT_TEMPLATE
5. Prepend SYSTEM_PROMPT
6. Return complete prompt string

### `_store_messages(...) -> dict`

**Process:**
1. Store user message: role="user", content=query, classification=class_result
2. Store assistant message: role="assistant", content=full_response, sources=sources, confidence=confidence, tokens_used=count
3. Update session last_active timestamp
4. Return {message_id, session_id}

---

## 15. SSE Event Formatting

Each event must follow the SSE standard:

```
event: {event_name}
data: {json_string}

```

Note the double newline after data — this is required by the SSE spec.

---

## 16. Rules for Implementation

- **Classification gates everything**: No retrieval for non-HR messages
- **Follow-ups rewritten before retrieval**: Original message stored, rewritten used for search
- **Confidence gate prevents hallucination**: Low/no confidence → no LLM generation
- **Sources always returned**: Every assistant response includes source citations
- **Conversation history in prompt**: Last N messages for context continuity
- **User personalization**: Greetings use user's full_name from User model
- **Messages stored after streaming**: Both query and response persisted
- **Session management**: Auto-create session if none provided, validate ownership
- **Error containment**: Errors at any step yield error SSE event, don't crash
- **Graceful degradation**: If one component fails, return helpful error message
- **Streaming is primary interface**: Test endpoint is for debugging only
- **Service returns async iterator**: Never HTTP response objects
- **Thin controllers**: Routes parse request, call service, format SSE output
- **All prompts in prompts module**: No hardcoded prompt strings in services
- **Timing tracked per step**: For performance monitoring and optimization
- **Token counting**: Track tokens used per response for cost monitoring

---

## 17. Edge Cases

| Scenario | Handling |
|----------|----------|
| Empty query | 422 validation error |
| Query > 2000 chars | 422 validation error |
| Session ID belongs to different user | 403 "Session does not belong to authenticated user" |
| No documents ingested | Search returns empty, hard fallback response |
| All chunks below min_score | Confidence gate → hard fallback |
| Gemini API timeout during generation | Error SSE event, suggest retry |
| Database write fails after generation | Log error, still return response to user |
| Classification fails | Error SSE event with classification_failed type |
| Search service fails | Error SSE event with retrieval_failed type |
| User sends exact same query twice | Process normally (may return same answer) |
| Multiple rapid queries | Rate limiting (Feature 11) — not blocking for now |
| Non-English query | Gemini handles translation, classify as hr_question |

---

## 18. Performance Targets

| Metric | Target |
|--------|--------|
| Classification | < 300ms |
| Query rewriting | < 500ms |
| Retrieval (embedding + search) | < 100ms |
| First token (TTFT) | < 1500ms total |
| Tokens per second (streaming) | > 30 tokens/sec |
| Total processing (excluding streaming) | < 2000ms |

---

## 19. Verification Steps

### Test with seeded data:

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@company.com","password":"john123"}' | jq -r '.access_token')

# 1. Test greeting
curl -X POST http://localhost:8000/api/v1/query/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "hi"}'

# Expected: classification=greeting_only, direct response with John's name

# 2. Test HR question
curl -X POST http://localhost:8000/api/v1/query/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "What is the remote work policy?"}'

# Expected: classification=hr_question, retrieved chunks, answer with sources

# 3. Test follow-up (use session_id from previous response)
curl -X POST http://localhost:8000/api/v1/query/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "explain that more clearly", "session_id": "SESSION_ID_FROM_STEP_2"}'

# Expected: classification=follow_up, rewritten query, contextual answer

# 4. Test out of domain
curl -X POST http://localhost:8000/api/v1/query/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "what is the capital of France"}'

# Expected: classification=out_of_domain, direct response

# 5. Test streaming
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  -d '{"query": "Tell me about leave policy"}' \
  --no-buffer

# 6. Test health
curl http://localhost:8000/api/v1/query/health
```

---

## 20. Definition of Done

### Core Functionality:
- [ ] `POST /api/v1/query` streams tokens via SSE correctly
- [ ] `POST /api/v1/query/test` returns complete debug response
- [ ] Classification routes to correct handler (retrieve vs direct)
- [ ] Follow-up queries rewritten before retrieval
- [ ] Retrieved context included in LLM prompt
- [ ] Answers cite sources (document, page, section)
- [ ] Confidence gate works for all 4 tiers
- [ ] "I don't know" responses for low/no confidence
- [ ] Direct responses for non-retrieval classifications
- [ ] User's name used in personalized greetings
- [ ] Conversation history in prompt (last 6 exchanges)
- [ ] Both query and response stored in messages table
- [ ] Session updated on each interaction

### Streaming:
- [ ] SSE events: token, sources, done, error
- [ ] Tokens streamed with minimal delay
- [ ] Sources event sent after final token
- [ ] Done event has complete metadata
- [ ] Error events contain actionable detail

### End-to-End:
- [ ] Works with all previous features integrated
- [ ] Health endpoint shows component status
- [ ] Pipeline step timings tracked
- [ ] Error handling at every step
- [ ] No hardcoded prompts in route handlers
- [ ] Service layer is framework-agnostic
- [ ] All prompts in prompts module
- [ ] All verification tests pass
- [ ] Response time within performance targets