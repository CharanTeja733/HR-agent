"""Document chunk schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    content: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    chunk_index: int
    access_level: str = "all"
