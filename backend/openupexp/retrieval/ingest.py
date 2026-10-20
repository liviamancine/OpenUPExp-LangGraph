"""Ingestão de fontes e construção incremental de versões do corpus."""

import hashlib
import re
import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.config import get_settings
from openupexp.db.models import Chunk, CorpusVersion, SourceDocument
from openupexp.retrieval.chunkers import CHUNKER_VERSION, Page, chunk_document, guess_source_kind, slug
from openupexp.retrieval.embeddings import Embedder

REFERENCE_KINDS = ("lei", "manual", "academico")
ELICITATION_KINDS = ("elicitacao",)


def extract_pages(filename: str, data: bytes) -> list[Page]:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return [Page(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    text = data.decode("utf-8", errors="replace")
    return [Page(1, text)]


async def add_source(
    session: AsyncSession,
    project_id: uuid.UUID,
    filename: str,
    data: bytes,
    source_kind: str | None = None,
) -> SourceDocument:
    """Registra um documento (idempotente pelo hash do conteúdo)."""
    sha = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(SourceDocument).where(
            SourceDocument.project_id == project_id, SourceDocument.sha256 == sha
        )
    )
    if existing:
        existing.ativo = True
        return existing

    kind = source_kind or guess_source_kind(filename)
    folder = get_settings().data_dir / "projects" / str(project_id) / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha[:12]}_{Path(filename).name}"
    path.write_bytes(data)

    pages = extract_pages(filename, data)
    texto = "\n\n".join(p.texto for p in pages)
    doc = SourceDocument(
        project_id=project_id,
        arquivo=Path(filename).name,
        source_kind=kind,
        sha256=sha,
        storage_path=str(path),
        texto=texto,
        paginas=len(pages),
        meta={"paginas_vazias": sum(1 for p in pages if len(p.texto.strip()) < 50)},
    )
    session.add(doc)
    await session.flush()
    return doc


async def build_corpus_version(
    session: AsyncSession,
    project_id: uuid.UUID,
    embedder: Embedder,
    *,
    kinds: tuple[str, ...] = REFERENCE_KINDS,
    purpose: str = "reference",
    run_id: uuid.UUID | None = None,
) -> CorpusVersion:
    """Cria uma nova versão do corpus, reaproveitando embeddings de chunks inalterados.

    purpose="elicitation" indexa o material de elicitação (entrevistas, workshops…) de uma
    execução da Fase 2, separado da base de referência do projeto.
    """
    cv = CorpusVersion(
        project_id=project_id,
        purpose=purpose,
        run_id=run_id,
        embedding_provider=embedder.provider,
        embedding_model=embedder.model,
        embedding_dim=embedder.dim,
        chunker_version=CHUNKER_VERSION,
        status="building",
    )
    session.add(cv)
    await session.flush()

    # cache de embeddings por hash do texto, de versões anteriores com o mesmo modelo
    previous = await session.execute(
        select(Chunk.sha256, Chunk.embedding)
        .join(CorpusVersion, Chunk.corpus_version_id == CorpusVersion.id)
        .where(
            CorpusVersion.project_id == project_id,
            CorpusVersion.status == "ready",
            CorpusVersion.embedding_provider == embedder.provider,
            CorpusVersion.embedding_model == embedder.model,
        )
    )
    cache = {sha: emb for sha, emb in previous.all() if emb is not None}

    docs = (
        await session.scalars(
            select(SourceDocument).where(
                SourceDocument.project_id == project_id,
                SourceDocument.ativo.is_(True),
                SourceDocument.source_kind.in_(kinds),
            )
        )
    ).all()

    stats = {"documentos": 0, "chunks": 0, "embeddings_reaproveitados": 0, "embeddings_novos": 0}
    for doc in docs:
        pages = extract_pages(doc.arquivo, Path(doc.storage_path).read_bytes())
        drafts = chunk_document(slug(Path(doc.arquivo).stem), doc.source_kind, pages)
        missing = [d for d in drafts if d.sha256 not in cache]
        if missing:
            vectors = embedder.encode_passages([d.texto for d in missing])
            for d, v in zip(missing, vectors):
                cache[d.sha256] = v
        stats["embeddings_novos"] += len(missing)
        stats["embeddings_reaproveitados"] += len(drafts) - len(missing)
        for d in drafts:
            meta = dict(d.meta, arquivo=doc.arquivo)
            session.add(
                Chunk(
                    corpus_version_id=cv.id,
                    source_document_id=doc.id,
                    source_kind=doc.source_kind,
                    stable_key=d.stable_key,
                    texto=d.texto,
                    pagina=d.pagina,
                    meta=meta,
                    sha256=d.sha256,
                    embedding=cache[d.sha256],
                )
            )
        stats["documentos"] += 1
        stats["chunks"] += len(drafts)
        await session.flush()

    cv.status = "ready"
    cv.stats = stats
    await session.flush()
    return cv


async def latest_corpus_version(session: AsyncSession, project_id: uuid.UUID) -> CorpusVersion | None:
    return await session.scalar(
        select(CorpusVersion)
        .where(CorpusVersion.project_id == project_id, CorpusVersion.status == "ready",
               CorpusVersion.purpose == "reference")
        .order_by(CorpusVersion.created_at.desc())
        .limit(1)
    )


async def latest_scope_document(session: AsyncSession, project_id: uuid.UUID) -> SourceDocument | None:
    return await session.scalar(
        select(SourceDocument)
        .where(
            SourceDocument.project_id == project_id,
            SourceDocument.source_kind == "escopo",
            SourceDocument.ativo.is_(True),
        )
        .order_by(SourceDocument.created_at.desc())
        .limit(1)
    )


def clean_scope_text(texto: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", texto).strip()
