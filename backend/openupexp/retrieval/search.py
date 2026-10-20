"""Busca híbrida: full-text (português) + vetorial, fundidas por RRF.

Referências normativas explícitas na consulta ("art. 20", "Lei 13.709") são
resolvidas por metadado, de forma exata, antes do ranking.
"""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.retrieval.embeddings import Embedder

RRF_K = 60
CANDIDATES = 50

_ART_REF = re.compile(r"\bart(?:igo)?s?\.?\s*(\d+)", re.IGNORECASE)
_LAW_REF = re.compile(r"\b(\d{1,2}\.\d{3})(?:/\d{2,4})?\b")


@dataclass
class ChunkHit:
    id: uuid.UUID
    stable_key: str
    texto: str
    pagina: int | None
    source_kind: str
    meta: dict
    score: float
    via: list[str] = field(default_factory=list)

    @property
    def ref(self) -> str:
        return f"chunk:{self.stable_key}"


def explicit_refs(query: str) -> tuple[list[str], list[str]]:
    return _ART_REF.findall(query), _LAW_REF.findall(query)


_SELECT = """
    SELECT c.id, c.stable_key, c.texto, c.pagina, c.source_kind, c.meta
    FROM chunk c
"""


async def hybrid_search(
    session: AsyncSession,
    corpus_version_id: uuid.UUID,
    query: str,
    embedder: Embedder,
    k: int = 10,
    kinds: list[str] | None = None,
    mode: str = "hybrid",
) -> list[ChunkHit]:
    kinds = kinds or ["lei", "manual", "academico"]
    params = {"cv": corpus_version_id, "kinds": kinds, "q": query, "n": CANDIDATES}
    ranked: dict[uuid.UUID, ChunkHit] = {}

    def add(rows, label: str, weight: float = 1.0):
        for rank, r in enumerate(rows, start=1):
            hit = ranked.get(r.id)
            if hit is None:
                hit = ChunkHit(r.id, r.stable_key, r.texto, r.pagina, r.source_kind, r.meta, 0.0)
                ranked[r.id] = hit
            hit.score += weight / (RRF_K + rank)
            hit.via.append(label)

    if mode in ("hybrid", "lexical"):
        rows = (
            await session.execute(
                text(
                    _SELECT
                    + """
                    , websearch_to_tsquery('portuguese', :q) q
                    WHERE c.corpus_version_id = :cv AND c.source_kind = ANY(:kinds) AND c.tsv @@ q
                    ORDER BY ts_rank_cd(c.tsv, q) DESC
                    LIMIT :n
                    """
                ),
                params,
            )
        ).all()
        if not rows:
            # websearch exige todos os termos; cai para OR entre os termos
            terms = [t for t in re.findall(r"\w{3,}", query.lower())][:30]
            if terms:
                rows = (
                    await session.execute(
                        text(
                            _SELECT
                            + """
                            , to_tsquery('portuguese', :oq) q
                            WHERE c.corpus_version_id = :cv AND c.source_kind = ANY(:kinds)
                              AND c.tsv @@ q
                            ORDER BY ts_rank_cd(c.tsv, q) DESC
                            LIMIT :n
                            """
                        ),
                        dict(params, oq=" | ".join(terms)),
                    )
                ).all()
        add(rows, "lexical")

    if mode in ("hybrid", "vector"):
        qvec = embedder.encode_query(query)
        rows = (
            await session.execute(
                text(
                    _SELECT
                    + """
                    WHERE c.corpus_version_id = :cv AND c.source_kind = ANY(:kinds)
                      AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> CAST(:qvec AS vector)
                    LIMIT :n
                    """
                ),
                dict(params, qvec=str(qvec)),
            )
        ).all()
        add(rows, "vector")

    arts, laws = explicit_refs(query)
    if arts:
        rows = (
            await session.execute(
                text(
                    _SELECT
                    + """
                    WHERE c.corpus_version_id = :cv AND c.source_kind = 'lei'
                      AND c.meta->>'artigo' = ANY(:arts)
                      AND (cardinality(CAST(:laws AS text[])) = 0 OR c.meta->>'lei_numero' = ANY(:laws))
                    ORDER BY c.stable_key
                    LIMIT :n
                    """
                ),
                dict(params, arts=arts, laws=laws),
            )
        ).all()
        add(rows, "explicit_ref", weight=10.0)

    return sorted(ranked.values(), key=lambda h: h.score, reverse=True)[:k]
