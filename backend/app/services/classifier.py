"""Service for classifying user messages and determining routing actions.

Uses Gemini 2.5 Flash for classification (LLM-powered, not rule-based)
to handle mixed intents, multilingual queries, and edge cases.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.core.constants import (
    CLASSIFICATION_ACTIONS,
    DIRECT_RESPONSES,
    VALID_CLASSIFICATIONS,
)
from app.core.exceptions import ClassificationError
from app.prompts.classifier import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFICATION_USER_PROMPT,
)
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)


class ClassifierService:
    """Service for classifying user messages and determining routing actions.

    Uses Gemini 2.5 Flash for classification (LLM-powered, not rule-based)
    to handle mixed intents, multilingual queries, and edge cases.
    """

    # Default confidence when LLM doesn't provide one
    DEFAULT_CONFIDENCE = 0.90

    def __init__(self, gemini_service: GeminiService):
        """Initialize with GeminiService instance.

        Args:
            gemini_service: Initialized GeminiService for LLM calls.
        """
        self.gemini = gemini_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify(
        self,
        message: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """Classify a user message and determine the required action.

        Args:
            message: The user's message text.
            conversation_history: List of recent messages for context.
                Format: ``[{"role": "user/assistant", "content": "..."}]``

        Returns:
            dict with:
                - message: The original message
                - classification: One of the 5 valid categories
                - confidence: Confidence score (0.0-1.0)
                - requires_retrieval: Whether vector search is needed
                - requires_rewriting: Whether query rewriting is needed
                - action: The action to take (retrieve, respond_directly, etc.)
                - direct_response: Pre-defined response (None for retrieval categories)
                - processing_time_ms: Time taken for classification

        Raises:
            ClassificationError: If classification fails after retries.
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
            logger.error("Classification failed: %s", e)
            raise ClassificationError(
                f"Failed to classify message: {e}",
                original_error=e,
            )

        # Guard against None response (e.g. content blocked by safety filter)
        if raw_response is None:
            logger.warning(
                "Gemini returned None for classification — falling back to hr_question"
            )
            raw_response = ""

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
            "Classification: '%s...' → %s (confidence: %.2f, %.0fms)",
            message[:50],
            classification,
            confidence,
            elapsed_ms,
        )

        return result

    def get_direct_response(
        self, classification: str, user_name: str = None
    ) -> str:
        """Get the pre-defined direct response for a classification.

        Args:
            classification: One of the valid classification categories.
            user_name: Optional user name for personalization.

        Returns:
            Response string. Returns empty string for unknown classifications.
        """
        response = DIRECT_RESPONSES.get(classification, "")

        if user_name and classification == "greeting_only":
            # Personalize greeting with user's name
            response = response.replace(
                "Hello!",
                f"Hello {user_name}!",
            )

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_history(self, history: list[dict]) -> str:
        """Format conversation history for the prompt.

        Args:
            history: List of message dicts with 'role' and 'content'.

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
        """Parse the LLM classification response.

        Handles various response formats:
        - ``"hr_question"``
        - ``"hr_question (confidence: 0.95)"``
        - ``"Classification: hr_question"``
        - ``"hr_question\\nconfidence: 0.9"``

        Args:
            raw_response: Raw text from LLM.

        Returns:
            Tuple of ``(classification, confidence)``.
            Falls back to ``("hr_question", 0.5)`` on invalid responses.
        """
        # Clean the response
        response = raw_response.strip().lower()
        logger.debug("Raw classification response: '%s'", raw_response[:200])

        # Remove common prefixes
        prefixes = ["classification:", "category:", "class:", "label:"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()

        # Extract just the first word (the classification)
        first_word = response.split()[0] if response else ""
        # Remove any trailing punctuation and trailing underscores
        first_word = first_word.rstrip(".,;:!?_")

        # Try to extract confidence
        confidence = self.DEFAULT_CONFIDENCE
        if "confidence:" in response:
            try:
                conf_str = response.split("confidence:")[-1].strip()
                confidence = float(conf_str.split()[0])
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, IndexError):
                pass

        # Validate classification — try exact match first, then fuzzy match
        if first_word in VALID_CLASSIFICATIONS:
            return first_word, confidence

        # Fuzzy match: handle truncated outputs like "greeting" -> "greeting_only"
        fuzzy_map = {
            "greeting": "greeting_only",
            "bot": "bot_question",
            "out": "out_of_domain",
            "follow": "follow_up",
            "hr": "hr_question",
        }
        if first_word in fuzzy_map:
            logger.debug(
                "Fuzzy-matched truncated classification '%s' -> '%s'",
                first_word,
                fuzzy_map[first_word],
            )
            return fuzzy_map[first_word], confidence

        # Fallback: unrecognized classification
        logger.warning(
            "Invalid classification '%s' from response '%s'. "
            "Falling back to 'hr_question'.",
            first_word,
            raw_response[:100],
        )
        return "hr_question", 0.5
