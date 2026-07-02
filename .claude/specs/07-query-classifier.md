# Feature 7: Query Classifier

## 1. Overview

Build the query classification system that analyzes every user message and routes it to the appropriate handler. The classifier determines whether a message is a greeting, bot question, out-of-domain query, follow-up to previous conversation, or a genuine HR question requiring retrieval.

This establishes the **routing intelligence** — the agent now knows what to do with each message instead of blindly retrieving for everything.

---

## 2. Depends on

- **Feature 1: Project Setup & Docker Environment** — services running
- **Feature 3: User Authentication** — user context available
- **Feature 6: Gemini Service Layer** — `GeminiService` handles all LLM calls

---

## 3. Routes

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/v1/classify` | Yes (JWT) | Classify a message (for testing/debugging) |

---

## 4. Route Specification

### `POST /api/v1/classify`

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

---

## 5. Classification Categories & Actions

| Classification | Action | Requires Retrieval | Requires Rewriting | Example |
|---------------|--------|-------------------|-------------------|---------|
| `greeting_only` | `respond_directly` | No | No | "hi", "thanks", "good morning" |
| `bot_question` | `respond_directly` | No | No | "what are you", "who made you" |
| `out_of_domain` | `respond_directly` | No | No | "what is water", "tell me a joke" |
| `follow_up` | `rewrite_then_retrieve` | Yes | Yes | "explain that more", "what about the second point" |
| `hr_question` | `retrieve` | Yes | No | "what is remote work policy", "how many leave days" |

---

## 6. Classification Approach

- **LLM-powered, not rule-based** — uses Gemini 2.5 Flash with a specialized prompt
- Handles mixed intents ("hi, explain X"), multilingual queries, implicit follow-ups
- Low temperature (0.1) for deterministic output
- Max 50 tokens output — just the classification word
- Safe default: invalid responses fallback to `hr_question`

---

## 7. Classification Prompt Design

- System prompt defines 5 categories with rules and examples
- Includes few-shot examples covering edge cases
- User prompt includes formatted conversation history (last 6 messages)
- Conversation history formatted as "User: ..." / "Assistant: ..."
- Empty history shows "No previous conversation."

---

## 8. Direct Response Templates

Each non-retrieval classification has a pre-defined response:

- **greeting_only**: Friendly greeting introducing the bot's capabilities
- **bot_question**: Explains what the bot is and what it can do
- **out_of_domain**: Politely redirects to HR topics with examples of what the bot can help with

---

## 9. New Folder Structure

```
backend/app/
├── api/v1/
│   └── classify.py           # Classification endpoint
├── services/
│   └── classifier.py         # Classification business logic
├── prompts/
│   ├── __init__.py
│   └── classifier.py         # Classification prompt templates
├── schemas/
│   └── classify.py           # Request/response schemas
└── core/
    └── constants.py           # Classification constants & direct responses
```

---

## 10. Files to Create

- `app/prompts/__init__.py` — empty package init
- `app/prompts/classifier.py` — system prompt + user prompt template
- `app/schemas/classify.py` — ClassifyRequest, ClassifyResponse, ConversationMessage schemas
- `app/services/classifier.py` — ClassifierService with classify() and get_direct_response()
- `app/api/v1/classify.py` — thin route handler for POST /api/v1/classify
- `app/core/constants.py` — VALID_CLASSIFICATIONS, CLASSIFICATION_ACTIONS, DIRECT_RESPONSES

---

## 11. Files to Change

- `app/main.py` — add classify router at `/api/v1/classify`
- `app/core/exceptions.py` — add `ClassificationError` exception

---

## 12. ClassifierService Methods

### `classify(message, conversation_history) -> dict`
- Formats conversation history for prompt
- Builds full prompt from templates
- Calls GeminiService.generate() with temperature=0.1, max_tokens=50
- Parses response to extract classification and confidence
- Falls back to `hr_question` if response is invalid
- Returns dict with classification, confidence, action flags, processing time

### `get_direct_response(classification, user_name=None) -> str`
- Returns pre-defined response for non-retrieval categories
- Personalizes greeting with user name if available

### `_format_history(history) -> str`
- Formats last 6 messages as "User: ..." / "Assistant: ..."
- Truncates long messages to 200 chars
- Returns "No previous conversation." if history is empty

### `_parse_response(raw_response) -> tuple[str, float]`
- Extracts classification word from LLM response
- Handles various response formats (with/without prefixes, extra text)
- Extracts confidence score if provided
- Validates classification is one of the 5 valid categories

---

## 13. Dependencies

All already in `requirements.txt` — no new packages required.

---

## 14. Rules for Implementation

- **LLM-powered only** — no keyword matching or if-else classification chains
- **Gemini 2.5 Flash** — temperature 0.1, max 50 tokens
- **Safe default** — invalid responses fallback to `hr_question` (triggers retrieval, safest)
- **Mixed intents** — "hi, explain X" must classify as `hr_question`, not `greeting_only`
- **Follow-ups need history** — `follow_up` only when conversation history exists with references
- **No retrieval for non-HR** — greetings, bot questions, out-of-domain get direct responses
- **Service returns dicts** — framework-agnostic, never HTTP responses
- **Thin controller** — route validates, calls service, returns response
- **Confidence always returned** — default 0.90 if LLM doesn't provide one
- **Multilingual support** — prompt includes non-English examples

---

## 15. Prompt Template Structure

### System Prompt Contains:
- Role definition: "query classifier for an HR Q&A assistant"
- 5 category definitions with examples
- 6 classification rules covering edge cases
- 12 few-shot examples demonstrating each category and tricky cases

### User Prompt Contains:
- Formatted conversation history (or "No previous conversation.")
- The user message to classify
- Instruction: "CLASSIFICATION (reply with exactly one word):"

---

## 16. Few-Shot Examples Included in Prompt

Must include these cases:
- Simple greeting → greeting_only
- Mixed greeting + question → hr_question
- Thanks/acknowledgment → greeting_only
- Bot identity question → bot_question
- Out-of-domain knowledge question → out_of_domain
- Explicit follow-up reference → follow_up
- Non-English HR question → hr_question
- New topic question → hr_question
- Context-dependent reference → follow_up

---

## 17. Response Parsing Logic

Handle these LLM response formats:
- `"hr_question"`
- `"hr_question (confidence: 0.95)"`
- `"Classification: hr_question"`
- `"hr_question\nconfidence: 0.9"`
- `"The classification is hr_question"`

Parsing steps:
1. Strip and lowercase response
2. Remove common prefixes (classification:, category:, class:, label:)
3. Extract first word as classification
4. Try to extract confidence from "confidence: X" pattern
5. Validate first word is in VALID_CLASSIFICATIONS
6. If invalid → log warning, return "hr_question" with 0.5 confidence

---

## 18. Expected Behavior

| User Message | History | Classification | Action |
|-------------|---------|----------------|--------|
| "hi" | None | greeting_only | respond_directly |
| "hello, what is remote work?" | None | hr_question | retrieve |
| "thanks, got it" | Exists | greeting_only | respond_directly |
| "what are you" | None | bot_question | respond_directly |
| "what is the weather" | None | out_of_domain | respond_directly |
| "explain that more" | Exists | follow_up | rewrite_then_retrieve |
| "how does that work" | Exists | follow_up | rewrite_then_retrieve |
| "hola, política de vacaciones" | None | hr_question | retrieve |
| "tell me a joke" | None | out_of_domain | respond_directly |
| "who made you" | None | bot_question | respond_directly |
| "what about paternity leave?" | None | hr_question | retrieve |
| "and the second point?" | Exists | follow_up | rewrite_then_retrieve |

---

## 19. Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty message | 422 validation error |
| Message > 2000 chars | 422 validation error |
| Gemini API fails | ClassificationError → 500 response |
| LLM returns invalid category | Log warning, fallback to hr_question |
| LLM returns extra text | Parse first word only |
| No conversation history | Prompt shows "No previous conversation." |

---

## 20. Definition of Done

- [ ] `POST /api/v1/classify` endpoint returns correct classification
- [ ] Classification uses Gemini 2.5 Flash (not rules-based)
- [ ] All 5 categories correctly identified for test cases
- [ ] Mixed intents resolved ("hi, explain X" → hr_question)
- [ ] Follow-ups detected only when conversation history exists
- [ ] Out-of-domain queries identified
- [ ] Bot meta-questions identified
- [ ] Multilingual queries handled
- [ ] Direct response templates for 3 non-retrieval categories
- [ ] Action mapping correct for all classifications
- [ ] requires_retrieval flag correctly set
- [ ] requires_rewriting flag correctly set
- [ ] Invalid LLM responses fallback to hr_question
- [ ] Confidence score always present in response
- [ ] Processing time tracked and returned
- [ ] Gemini errors raise ClassificationError
- [ ] Prompt templates separated from business logic
- [ ] Constants centralized in core/constants.py
- [ ] Service returns dicts, not HTTP responses
- [ ] Route handler is thin (validation only)
- [ ] Classification completes in <300ms typical