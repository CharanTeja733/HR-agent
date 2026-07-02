"""Gemini embedding utility — thin wrapper around :class:`GeminiService`.

..  note::

    All Gemini SDK interactions now happen in
    :class:`app.services.gemini.GeminiService`.  This module exists for
    backward compatibility and convenience — it creates a fresh
    ``GeminiService`` per call and delegates.
"""

from __future__ import annotations

from app.core.exceptions import EmbeddingGenerationError, GeminiEmbeddingError
from app.services.gemini import GeminiService


async def embed_texts(
    texts: list[str],
    api_key: str,
    model: str = "gemini-embedding-001",        # noqa: ARG001 — backward compat
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = 768,            # noqa: ARG001 — backward compat
    batch_size: int = 50,
    max_retries: int = 3,                        # noqa: ARG001 — backward compat
) -> list[list[float]]:
    """Generate embeddings for *texts* using the Gemini embedding model.

    Delegates to :class:`GeminiService`.  The *model*, *output_dimensionality*,
    and *max_retries* parameters are accepted for backward compatibility but
    are not forwarded — ``GeminiService`` is the single source of truth for
    model names and retry configuration.

    Parameters
    ----------
    texts : list[str]
        The texts to embed.
    api_key : str
        Google Gemini API key.
    model : str
        Ignored — kept for backward compatibility.
    task_type : str
        ``"RETRIEVAL_DOCUMENT"`` or ``"RETRIEVAL_QUERY"``.
    output_dimensionality : int
        Ignored — kept for backward compatibility.
    batch_size : int
        Number of texts per API call (default: 50).
    max_retries : int
        Ignored — kept for backward compatibility.

    Returns
    -------
    list[list[float]]
        One embedding vector per input text.

    Raises
    ------
    EmbeddingGenerationError
        If all retries are exhausted.
    """
    if not texts:
        return []

    service = GeminiService(api_key)
    try:
        return await service.embed_texts(
            texts=texts,
            task_type=task_type,
            batch_size=batch_size,
        )
    except GeminiEmbeddingError as exc:
        raise EmbeddingGenerationError(attempts=3) from exc


async def embed_single(
    text: str,
    api_key: str,
    model: str = "gemini-embedding-001",  # noqa: ARG001 — backward compat
) -> list[float]:
    """Convenience wrapper — embed a single text and return its vector.

    Delegates to :class:`GeminiService`.
    """
    service = GeminiService(api_key)
    try:
        return await service.embed_single(text, task_type="RETRIEVAL_QUERY")
    except GeminiEmbeddingError as exc:
        raise EmbeddingGenerationError(attempts=3) from exc
