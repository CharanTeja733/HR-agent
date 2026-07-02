"""Document repository — specialized queries for the hr_documents table."""

from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import HRDocument
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[HRDocument]):
    """Data-access layer for ``hr_documents``.

    Extends ``BaseRepository`` with document-specific queries.
    Methods that mutate data use ``flush()`` rather than ``commit()`` so
    the caller (``IngestionService``) can manage transaction boundaries.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(HRDocument, db)

    # ------------------------------------------------------------------
    # Source-based queries
    # ------------------------------------------------------------------

    async def get_by_source(self, source: str) -> list[HRDocument]:
        """Return all chunks for *source*, ordered by chunk_index."""
        result = await self.db.execute(
            select(HRDocument)
            .where(HRDocument.source == source)
            .order_by(HRDocument.chunk_index)
        )
        return list(result.scalars().all())

    async def delete_by_source(self, source: str) -> int:
        """Delete all chunks for *source*.  Returns the number of rows deleted.

        Uses ``execute()`` + ``flush()`` — the caller is responsible for
        calling ``commit()``.
        """
        result = await self.db.execute(
            delete(HRDocument).where(HRDocument.source == source)
        )
        await self.db.flush()
        return result.rowcount

    async def insert_chunks(self, chunks: list[dict]) -> list[HRDocument]:
        """Bulk-insert *chunks* and flush to the database.

        Each dict must contain keys matching ``HRDocument`` columns:
        content, embedding, source, chunk_index, access_level,
        and optionally page, section.

        Uses ``add_all()`` + ``flush()`` — the caller is responsible for
        calling ``commit()``.
        """
        instances = [HRDocument(**chunk) for chunk in chunks]
        self.db.add_all(instances)
        await self.db.flush()
        return instances

    async def source_exists(self, source: str) -> bool:
        """Return ``True`` if at least one chunk exists for *source*."""
        result = await self.db.execute(
            select(HRDocument.id).where(HRDocument.source == source).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Aggregation queries
    # ------------------------------------------------------------------

    async def list_documents(self) -> list[dict]:
        """Return one row per unique source with chunk count and metadata.

        This uses a raw textual query because SQLAlchemy's ORM GROUP BY on
        multiple non-aggregated columns is verbose.
        """
        query = text("""
            SELECT
                source,
                COUNT(*)            AS chunk_count,
                MAX(access_level)   AS access_level,
                MAX(created_at)     AS ingested_at
            FROM hr_documents
            GROUP BY source
            ORDER BY source
        """)
        result = await self.db.execute(query)
        return [
            {
                "source": row.source,
                "chunk_count": row.chunk_count,
                "access_level": row.access_level,
                "ingested_at": row.ingested_at,
            }
            for row in result
        ]

    async def get_document_stats(self) -> dict:
        """Return aggregated statistics across all documents.

        Runs multiple queries to collect: total distinct sources, total
        chunks, total characters, access-level distribution, largest
        document, and last ingestion timestamp.
        """
        # Total distinct sources
        total_sources_result = await self.db.execute(
            select(func.count(func.distinct(HRDocument.source)))
        )
        total_documents = total_sources_result.scalar_one()

        # Total chunks and characters
        totals_result = await self.db.execute(
            select(
                func.count(HRDocument.id),
                func.coalesce(func.sum(func.char_length(HRDocument.content)), 0),
                func.max(HRDocument.created_at),
            )
        )
        total_chunks, total_characters, last_ingested = totals_result.one()

        # Access-level distribution
        dist_result = await self.db.execute(
            select(
                HRDocument.access_level,
                func.count(HRDocument.id),
            ).group_by(HRDocument.access_level)
        )
        dist_rows = {row.access_level: row.count for row in dist_result}
        access_level_dist = {
            "all": dist_rows.get("all", 0),
            "manager": dist_rows.get("manager", 0),
            "hr_admin": dist_rows.get("hr_admin", 0),
        }

        # Largest document (by chunk count)
        largest_query = text("""
            SELECT source, COUNT(*) AS cnt
            FROM hr_documents
            GROUP BY source
            ORDER BY cnt DESC
            LIMIT 1
        """)
        largest_result = await self.db.execute(largest_query)
        largest_row = largest_result.first()
        largest_document = largest_row.source if largest_row else None

        return {
            "total_documents": total_documents or 0,
            "total_chunks": total_chunks or 0,
            "total_characters": total_characters or 0,
            "access_level_distribution": access_level_dist,
            "largest_document": largest_document,
            "last_ingested": last_ingested,
        }

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    async def search_similar(
        self,
        query_embedding: list[float],
        access_levels: list[str],
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Perform cosine similarity search using pgvector.

        Parameters
        ----------
        query_embedding : list[float]
            768-dimensional embedding vector for the query.
        access_levels : list[str]
            Allowed access levels (e.g. ``["all", "manager"]``).
        top_k : int
            Maximum number of results to return.
        min_score : float
            Minimum similarity score (0.0 to 1.0).

        Returns
        -------
        list[dict]
            Each dict has keys: id, content, source, page, section, score.
            Results are ordered by similarity score descending.
        """
        # Format the embedding as a pgvector-compatible literal string
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # NOTE: ``\:`` escapes colons in SQLAlchemy text() so that the
        # PostgreSQL ``::vector`` cast operator is preserved literally.
        query = text(r"""
            SELECT
                id,
                content,
                source,
                page,
                section,
                1 - (embedding <=> :embedding\:\:vector) AS score
            FROM hr_documents
            WHERE
                access_level = ANY(:access_levels)
                AND 1 - (embedding <=> :embedding\:\:vector) >= :min_score
            ORDER BY embedding <=> :embedding\:\:vector
            LIMIT :top_k
        """)

        result = await self.db.execute(
            query,
            {
                "embedding": embedding_str,
                "access_levels": access_levels,
                "min_score": min_score,
                "top_k": top_k,
            },
        )

        return [
            {
                "id": row.id,
                "content": row.content,
                "source": row.source,
                "page": row.page,
                "section": row.section,
                "score": float(row.score),
            }
            for row in result
        ]

    async def get_total_indexed_count(self) -> int:
        """Return the total number of chunks in ``hr_documents``."""
        result = await self.db.execute(
            select(func.count(HRDocument.id))
        )
        return result.scalar_one()

    async def check_vector_index_exists(self) -> bool:
        """Check whether the IVFFlat index on ``hr_documents.embedding`` exists."""
        query = text("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE indexname = 'idx_hr_documents_embedding'
            )
        """)
        result = await self.db.execute(query)
        return result.scalar_one()
