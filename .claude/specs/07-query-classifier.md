# Feature 7: Query Classifier

## 1. Overview

Build the query classification system that analyzes every user message and routes it to the appropriate handler. The classifier determines whether a message is a greeting, bot question, out-of-domain query, follow-up to previous conversation, or a genuine HR question requiring retrieval.

This establishes the **routing intelligence** — the agent now knows what to do with each message instead of blindly retrieving for everything.

---

## 2. Depends on

- **Feature 1: Project Setup & Docker Environment** — services running
- **Feature 3: User Authentication** — user context available (for personalization)
- **Feature 6: Gemini Service Layer** — `GeminiService` handles all LLM calls

---

## 3. Routes

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/v1/classify` | Yes (JWT) | Classify a message (for testing/debugging) |

---

## 4. Route Specification

### `POST /api/v1/classify`

**Headers:** `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "message": "hi, explain about remote work policy",
  "conversation_history": [
    {"role": "user", "content": "What is leave policy?"},
    {"role": "assistant", "content": "Our leave policy provides 20 days..."}
  ]
}
```

**Success Response (200):**
```json
{
  "message": "hi, explain about remote work policy",
  "classification": "hr_question",
  "confidence": 0.95,
  "requires_retrieval": true,
  "requires_rewriting": false,
  "action": "retrieve",
  "processing_time_ms": 180
}
```

**Classification → Action Mapping:**
| Classification | Action | Requires Retrieval | Requires Rewriting |
|---------------|--------|-------------------|-------------------|
| `greeting_only` | `respond_directly` | No | No |
| `bot_question` | `respond_directly` | No | No |
| `out_of_domain` | `respond_directly` | No | No |
| `follow_up` | `rewrite_then_retrieve` | Yes | Yes |
| `hr_question` | `retrieve` | Yes | No |

---

## 5. Classification Logic

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    QUERY CLASSIFICATION — LLM-POWERED                                │
│                                                                                      │
│  The classifier uses Gemini 2.5 Flash with a specialized prompt.                     │
│  It's LLM-based (not rule-based) because:                                            │
│  • Handles mixed intents ("hi, explain X")                                          │
│  • Understands multiple languages ("hola, quiero saber...")                          │
│  • Detects out-of-domain queries ("what is water")                                   │
│  • Identifies bot meta-questions ("what are you")                                    │
│  • Recognizes implicit follow-ups ("what about the second point?")                   │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                                                                              │    │
│  │  USER MESSAGE                                                                │    │
│  │      │                                                                       │    │
│  │      ▼                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐      │    │
│  │  │  CLASSIFICATION PROMPT (sent to Gemini 2.5 Flash)                   │      │    │
│  │  │                                                                     │      │    │
│  │  │  Temperature: 0.1 (deterministic)                                   │      │    │
│  │  │  Max tokens: 50 (just the classification)                           │      │    │
│  │  └────────────────────────────────────────────────────────────────────┘      │    │
│  │      │                                                                       │    │
│  │      ▼                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐      │    │
│  │  │  OUTPUT PARSER                                                      │      │    │
│  │  │  • Extract classification from LLM response                         │      │    │
│  │  │  • Validate it's one of the 5 valid categories                      │      │    │
│  │  │  • Fallback to "hr_question" if response is invalid                 │      │    │
│  │  │  • Extract confidence score if provided                             │      │    │
│  │  └────────────────────────────────────────────────────────────────────┘      │    │
│  │      │                                                                       │    │
│  │      ▼                                                                       │    │
│  │  ┌────────────────────────────────────────────────────────────────────┐      │    │
│  │  │  ROUTING DECISION                                                   │      │    │
│  │  │  • Map classification to action                                     │      │    │
│  │  │  • Determine if retrieval is needed                                 │      │    │
│  │  │  • Determine if query rewriting is needed                           │      │    │
│  │  └────────────────────────────────────────────────────────────────────┘      │    │
│  │                                                                              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Classification Prompt

```
You are a query classifier for an HR Q&A assistant. Your job is to classify user messages into exactly one category.

CATEGORIES:
- greeting_only: Just a greeting, thanks, or small talk. Examples: "hi", "hello", "thanks", "good morning", "ok bye"
- bot_question: User is asking about you, the bot. Examples: "what are you", "who made you", "what can you do", "how do you work"
- out_of_domain: Not related to HR, policies, benefits, or work. Examples: "what is water", "tell me a joke", "stock price today"
- follow_up: References something from the previous conversation. Examples: "explain that more", "what about the second point", "how do I apply for it", "tell me more"
- hr_question: A question about HR topics, company policies, benefits, leave, payroll, remote work, or anything work-related. This includes questions that start with greetings like "hi, explain remote work policy".

RULES:
1. If a message contains BOTH a greeting AND an HR question → classify as "hr_question"
2. If a message references "that", "it", "this", "above", "previous", "second point" and there is conversation history → classify as "follow_up"
3. If the message is clearly not about HR/work → classify as "out_of_domain"
4. If asking about your capabilities or identity → classify as "bot_question"
5. If it's purely social/greeting with no question → classify as "greeting_only"
6. When in doubt between hr_question and something else, prefer hr_question (safe default)

CONVERSATION HISTORY:
{conversation_history}

USER MESSAGE: {user_message}

CLASSIFICATION (reply with exactly one word): 
```

---

## 7. Few-Shot Examples (Embedded in Prompt)

Include these examples in the system prompt for better accuracy:

```
EXAMPLES:

Message: "hi"
Classification: greeting_only

Message: "hello, what is the leave policy?"
Classification: hr_question

Message: "thanks, that helped a lot"
Classification: greeting_only

Message: "what are you"
Classification: bot_question

Message: "what is the capital of France"
Classification: out_of_domain

Message: "explain that in more detail"
Classification: follow_up

Message: "hola, quiero saber sobre la política de trabajo remoto"
Classification: hr_question

Message: "what about paternity leave?"
Classification: hr_question

Message: "how does that work for contractors?"
Classification: follow_up

Message: "what is water made of"
Classification: out_of_domain

Message: "who created you"
Classification: bot_question

Message: "good morning, can you tell me about health insurance?"
Classification: hr_question

Message: "and the second point you mentioned?"
Classification: follow_up
```

---

## 8. Direct Responses by Classification

Each non-retrieval classification has a pre-defined response template:

### greeting_only
```
"Hello! I'm your HR assistant. I can help you with questions about company policies, leave, benefits, remote work, and more. What would you like to know?"
```

### bot_question
```
"I'm an HR assistant bot designed to help employees with questions about company policies, benefits, leave, and other work-related topics. I use the company's official documents to provide accurate answers. How can I help you today?"
```

### out_of_domain
```
"I'm designed specifically to help with HR-related questions. I can assist you with topics like leave policies, benefits, remote work guidelines, payroll, and other company policies. Is there an HR topic I can help you with?"
```

---

## 9. New Folder Structure (This Feature Only)

```text
backend/app/
├── api/v1/
│   └── classify.py               # 🔵 PRESENTATION — classification endpoint
├── services/
│   └── classifier.py             # 🟢 BUSINESS LOGIC — classification service
├── prompts/
│   ├── __init__.py
│   └── classifier.py             # 📝 Classification prompt templates
├── schemas/
│   └── classify.py               # 📋 Classification request/response schemas
└── core/
    └── constants.py              # 🔧 Classification constants & responses
```

---

## 10. Files to Create

### Layer 1: Constants (`app/core/`)

#### `app/core/constants.py`

```python
"""Constants for query classification."""

# Valid classification categories
VALID_CLASSIFICATIONS = {
    "greeting_only",
    "bot_question",
    "out_of_domain",
    "follow_up",
    "hr_question",
}

# Classification → Action mapping
CLASSIFICATION_ACTIONS = {
    "greeting_only": "respond_directly",
    "bot_question": "respond_directly",
    "out_of_domain": "respond_directly",
    "follow_up": "rewrite_then_retrieve",
    "hr_question": "retrieve",
}

# Direct response templates
DIRECT_RESPONSES = {
    "greeting_only": (
        "Hello! I'm your HR assistant. I can help you with questions about "
        "company policies, leave, benefits, remote work, and more. "
        "What would you like to know?"
    ),
    "bot_question": (
        "I'm an HR assistant bot designed to help employees with questions "
        "about company policies, benefits, leave, and other work-related topics. "
        "I use the company's official documents to provide accurate answers. "
        "How can I help you today?"
    ),
    "out_of_domain": (
        "I'm designed specifically to help with HR-related questions. "
        "I can assist you with topics like leave policies, benefits, "
        "remote work guidelines, payroll, and other company policies. "
        "Is there an HR topic I can help you with?"
    ),
}

# Follow-up reference keywords (for logging/debugging only — LLM does the actual classification)
FOLLOW_UP_INDICATORS = [
    "explain more", "clarify", "elaborate", "tell me more",
    "what about", "and the", "that", "it", "this",
    "above", "previous", "second point", "first point",
    "how do i apply", "how does that work",
]
```

---

### Layer 2: Prompts (`app/prompts/`)

#### `app/prompts/__init__.py`

- Empty file

#### `app/prompts/classifier.py`

```python
"""Prompt templates for query classification."""

CLASSIFICATION_SYSTEM_PROMPT = """You are a query classifier for an HR Q&A assistant. Your job is to classify user messages into exactly one category.

CATEGORIES:
- greeting_only: Just a greeting, thanks, or small talk. Examples: "hi", "hello", "thanks", "good morning", "ok bye"
- bot_question: User is asking about you, the bot. Examples: "what are you", "who made you", "what can you do", "how do you work"
- out_of_domain: Not related to HR, policies, benefits, or work. Examples: "what is water", "tell me a joke", "stock price today"
- follow_up: References something from the previous conversation. Examples: "explain that more", "what about the second point", "how do I apply for it", "tell me more"
- hr_question: A question about HR topics, company policies, benefits, leave, payroll, remote work, or anything work-related. This includes questions that start with greetings like "hi, explain remote work policy".

RULES:
1. If a message contains BOTH a greeting AND an HR question → classify as "hr_question"
2. If a message references "that", "it", "this", "above", "previous", "second point" and there is conversation history → classify as "follow_up"
3. If the message is clearly not about HR/work → classify as "out_of_domain"
4. If asking about your capabilities or identity → classify as "bot_question"
5. If it's purely social/greeting with no question → classify as "greeting_only"
6. When in doubt between hr_question and something else, prefer hr_question (safe default)

EXAMPLES:
Message: "hi" → greeting_only
Message: "hello, what is the leave policy?" → hr_question
Message: "thanks, that helped a lot" → greeting_only
Message: "what are you" → bot_question
Message: "what is the capital of France" → out_of_domain
Message: "explain that in more detail" → follow_up
Message: "hola, quiero saber sobre la política de trabajo remoto" → hr_question
Message: "what about paternity leave?" → hr_question
Message: "how does that work for contractors?" → follow_up
Message: "what is water made of" → out_of_domain
Message: "who created you" → bot_question
Message: "good morning, can you tell me about health insurance?" → hr_question
Message: "and the second point you mentioned?" → follow_up"""


CLASSIFICATION_USER_PROMPT = """CONVERSATION HISTORY:
{conversation_history}

USER MESSAGE: {user_message}

CLASSIFICATION (reply with exactly one word):"""
```

---

### Layer 3: Schemas (`app/schemas/`)

#### `app/schemas/classify.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from app.core.constants import VALID_CLASSIFICATIONS


class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ClassifyRequest(BaseModel):
    """Request schema for message classification."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user message to classify"
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=[],
        description="Recent conversation messages for context"
    )


class ClassifyResponse(BaseModel):
    """Response schema for message classification."""
    message: str
    classification: str
    confidence: float
    requires_retrieval: bool
    requires_rewriting: bool
    action: str
    processing_time_ms: float

    @validator('classification')
    def validate_classification(cls, v):
        if v not in VALID_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification: {v}")
        return v
```

---

### Layer 4: Services (`app/services/`)

#### `app/services/classifier.py`

```python
import time
import logging
from typing import Optional
from app.services.gemini import GeminiService
from app.prompts.classifier import CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_USER_PROMPT
from app.core.constants import (
    VALID_CLASSIFICATIONS,
    CLASSIFICATION_ACTIONS,
    DIRECT_RESPONSES,
)
from app.core.exceptions import ClassificationError

logger = logging.getLogger(__name__)


class ClassifierService:
    """
    Service for classifying user messages and determining routing actions.
    
    Uses Gemini 2.5 Flash for classification (LLM-powered, not rule-based)
    to handle mixed intents, multilingual queries, and edge cases.
    """
    
    # Default confidence when LLM doesn't provide one
    DEFAULT_CONFIDENCE = 0.90
    
    def __init__(self, gemini_service: GeminiService):
        """
        Initialize with GeminiService instance.
        
        Args:
            gemini_service: Initialized GeminiService for LLM calls
        """
        self.gemini = gemini_service
    
    async def classify(
        self,
        message: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        Classify a user message and determine the required action.
        
        Args:
            message: The user's message text
            conversation_history: List of recent messages for context
                Format: [{"role": "user/assistant", "content": "..."}]
        
        Returns:
            dict with:
                - classification: One of the 5 valid categories
                - confidence: Confidence score (0.0-1.0)
                - requires_retrieval: Whether vector search is needed
                - requires_rewriting: Whether query rewriting is needed
                - action: The action to take
                - direct_response: Pre-defined response (for non-retrieval categories)
        
        Raises:
            ClassificationError: If classification fails after retries
        """
        start_time = time.time()
        
        # Build conversation history string
        history_str = self._format_history(conversation_history or [])
        
        # Build classification prompt
        user_prompt = CLASSIFICATION_USER_PROMPT.format(
            conversation_history=history_str,
            user_message=message,
        )
        
        full_prompt = f"{CLASSIFICATION_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # Call Gemini for classification
        try:
            raw_response = await self.gemini.generate(
                prompt=full_prompt,
                temperature=0.1,
                max_output_tokens=50,
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            raise ClassificationError(f"Failed to classify message: {e}")
        
        # Parse and validate the response
        classification, confidence = self._parse_response(raw_response)
        
        # Determine actions
        requires_retrieval = classification in ("follow_up", "hr_question")
        requires_rewriting = classification == "follow_up"
        action = CLASSIFICATION_ACTIONS.get(classification, "retrieve")
        direct_response = DIRECT_RESPONSES.get(classification)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        result = {
            "message": message,
            "classification": classification,
            "confidence": confidence,
            "requires_retrieval": requires_retrieval,
            "requires_rewriting": requires_rewriting,
            "action": action,
            "direct_response": direct_response,
            "processing_time_ms": round(elapsed_ms, 2),
        }
        
        logger.info(
            f"Classification: '{message[:50]}...' → {classification} "
            f"(confidence: {confidence:.2f}, {elapsed_ms:.0f}ms)"
        )
        
        return result
    
    def _format_history(self, history: list[dict]) -> str:
        """
        Format conversation history for the prompt.
        
        Args:
            history: List of message dicts with 'role' and 'content'
        
        Returns:
            Formatted string or "No previous conversation."
        """
        if not history:
            return "No previous conversation."
        
        lines = []
        for msg in history[-6:]:  # Last 6 messages for context
            role = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"][:200]  # Truncate long messages
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
    
    def _parse_response(self, raw_response: str) -> tuple[str, float]:
        """
        Parse the LLM classification response.
        
        Handles various response formats:
        - "hr_question"
        - "hr_question (confidence: 0.95)"
        - "Classification: hr_question"
        - "hr_question\nconfidence: 0.9"
        
        Args:
            raw_response: Raw text from LLM
        
        Returns:
            Tuple of (classification, confidence)
        """
        # Clean the response
        response = raw_response.strip().lower()
        
        # Remove common prefixes
        prefixes = ["classification:", "category:", "class:", "label:"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Extract just the first word (the classification)
        first_word = response.split()[0] if response else ""
        # Remove any trailing punctuation
        first_word = first_word.rstrip(".,;:!?")
        
        # Try to extract confidence
        confidence = self.DEFAULT_CONFIDENCE
        if "confidence:" in response:
            try:
                conf_str = response.split("confidence:")[-1].strip()
                confidence = float(conf_str.split()[0])
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, IndexError):
                pass
        
        # Validate classification
        if first_word not in VALID_CLASSIFICATIONS:
            logger.warning(
                f"Invalid classification '{first_word}' from response '{raw_response}'. "
                f"Falling back to 'hr_question'."
            )
            return "hr_question", 0.5
        
        return first_word, confidence
    
    def get_direct_response(self, classification: str, user_name: str = None) -> str:
        """
        Get the pre-defined direct response for a classification.
        
        Args:
            classification: One of the valid classification categories
            user_name: Optional user name for personalization
        
        Returns:
            Response string
        """
        response = DIRECT_RESPONSES.get(classification, "")
        
        if user_name and classification == "greeting_only":
            # Personalize greeting with user's name
            response = response.replace(
                "Hello!",
                f"Hello {user_name}!"
            )
        
        return response
```

---

### Layer 5: API Routes (`app/api/v1/`)

#### `app/api/v1/classify.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.services.gemini import GeminiService
from app.services.classifier import ClassifierService
from app.schemas.classify import ClassifyRequest, ClassifyResponse
from app.models.user import User
from app.config import settings

router = APIRouter()


@router.post("/", response_model=ClassifyResponse)
async def classify_message(
    request: ClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Classify a user message for testing and debugging purposes.
    
    Returns the classification, confidence, and recommended action.
    This endpoint is useful for verifying the classifier behavior.
    """
    try:
        gemini_service = GeminiService(settings.GEMINI_API_KEY)
        classifier = ClassifierService(gemini_service)
        
        result = await classifier.classify(
            message=request.message,
            conversation_history=[
                msg.model_dump() for msg in request.conversation_history
            ] if request.conversation_history else None,
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )
```

---

## 11. Changes to Existing Files

### A. `backend/app/main.py`

```python
from app.api.v1 import classify

app.include_router(
    classify.router,
    prefix="/api/v1/classify",
    tags=["Classification"]
)
```

### B. `backend/app/core/exceptions.py`

Add classification exception:

```python
class ClassificationError(Exception):
    """Raised when query classification fails."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)
```

---

## 12. Files to Create

```
backend/app/prompts/__init__.py
backend/app/prompts/classifier.py
backend/app/schemas/classify.py
backend/app/services/classifier.py
backend/app/api/v1/classify.py
backend/app/core/constants.py
```

---

## 13. Files to Change

```
backend/app/main.py                     (add classify router)
backend/app/core/exceptions.py          (add ClassificationError)
```

---

## 14. Dependencies

All already in `requirements.txt` — no new packages.

---

## 15. Rules for Implementation

- **LLM-powered, not rule-based**: No keyword matching or if-else chains for classification
- **Gemini 2.5 Flash only**: Classification uses the fast, cheap model
- **Low temperature (0.1)**: Deterministic responses for consistent classification
- **Max 50 tokens output**: Classification is just one word
- **Safe default**: If classification fails or is invalid → fallback to `hr_question` (triggers retrieval, safest option)
- **No retrieval for non-HR**: Greetings, bot questions, and out-of-domain get direct responses
- **Follow-ups trigger rewriting**: `follow_up` classification → rewrite query → then retrieve
- **Mixed intents resolved correctly**: "hi, explain X" → `hr_question` (not greeting)
- **Multilingual support**: The LLM handles non-English queries naturally
- **Service returns dicts**: Framework-agnostic, usable from any context
- **Thin controller**: Route only validates request, calls service, returns response
- **Confidence tracked**: Always return a confidence score, default 0.90 if LLM doesn't provide one

---

## 16. Expected Behavior

### Classification examples:

| User Message | Conversation History | Classification | Action |
|-------------|---------------------|----------------|--------|
| `"hi"` | None | `greeting_only` | `respond_directly` |
| `"hello, what is remote work?"` | None | `hr_question` | `retrieve` |
| `"thanks, got it"` | Exists | `greeting_only` | `respond_directly` |
| `"what are you"` | None | `bot_question` | `respond_directly` |
| `"what is the weather"` | None | `out_of_domain` | `respond_directly` |
| `"explain that more"` | Exists | `follow_up` | `rewrite_then_retrieve` |
| `"how does that work"` | Exists | `follow_up` | `rewrite_then_retrieve` |
| `"hola, política de vacaciones"` | None | `hr_question` | `retrieve` |
| `"tell me a joke"` | None | `out_of_domain` | `respond_directly` |
| `"who made you"` | None | `bot_question` | `respond_directly` |
| `"what about paternity leave?"` | Exists (discussing leave) | `hr_question` | `retrieve` |
| `"and the second point?"` | Exists | `follow_up` | `rewrite_then_retrieve` |

### Edge cases:

1. **Empty message**: Validation rejects (min_length=1)
2. **Very long message**: Validated (max_length=2000), but LLM handles full text
3. **No conversation history**: "No previous conversation." in prompt
4. **Invalid LLM response**: Fallback to `hr_question` with confidence 0.5
5. **Gemini API failure**: Raises `ClassificationError`

---

## 17. Error Handling Expectations

| Scenario | Behavior |
|----------|----------|
| Empty message | 422 validation error |
| Message > 2000 chars | 422 validation error |
| Gemini API fails | `ClassificationError` raised, route returns 500 |
| LLM returns invalid category | Logged warning, fallback to `hr_question` |
| LLM returns extra text | Parsed to extract first word only |
| No conversation history | Empty string "No previous conversation." |

---

## 18. Verification Steps

```bash
# 1. Login to get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@company.com","password":"john123"}' \
  | jq -r '.access_token')

# 2. Test greeting
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "hi"}'

# Expected: classification="greeting_only", requires_retrieval=false

# 3. Test mixed greeting + HR question
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "hello, explain about remote work policy"}'

# Expected: classification="hr_question", requires_retrieval=true

# 4. Test follow-up with history
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "explain that more clearly",
    "conversation_history": [
      {"role": "user", "content": "What is remote work policy?"},
      {"role": "assistant", "content": "Our remote work policy allows 2 days per week..."}
    ]
  }'

# Expected: classification="follow_up", requires_retrieval=true, requires_rewriting=true

# 5. Test bot question
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "what are you"}'

# Expected: classification="bot_question", requires_retrieval=false

# 6. Test out of domain
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "what is water"}'

# Expected: classification="out_of_domain", requires_retrieval=false

# 7. Test multilingual
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "hola, quiero saber sobre la política de vacaciones"}'

# Expected: classification="hr_question", requires_retrieval=true
```

---

## 19. Definition of Done

- [ ] `POST /api/v1/classify` endpoint works (for testing)
- [ ] Classification uses Gemini 2.5 Flash (not rules)
- [ ] All 5 categories correctly identified
- [ ] Mixed intents resolved correctly ("hi, explain X" → hr_question)
- [ ] Follow-ups detected when conversation history exists
- [ ] Out-of-domain queries identified
- [ ] Bot meta-questions identified
- [ ] Multilingual queries handled
- [ ] Direct response templates for greeting, bot_question, out_of_domain
- [ ] Action mapping correct for each classification
- [ ] `requires_retrieval` flag correctly set
- [ ] `requires_rewriting` flag correctly set
- [ ] Invalid LLM responses fallback to `hr_question`
- [ ] Confidence score always returned
- [ ] Processing time tracked
- [ ] Gemini errors handled gracefully with `ClassificationError`
- [ ] Prompt templates separated from logic (in `app/prompts/`)
- [ ] Constants centralized in `app/core/constants.py`
- [ ] Service returns dicts, not HTTP responses
- [ ] Route is thin controller
- [ ] All verification tests pass
- [ ] Classification is fast (<300ms typical)