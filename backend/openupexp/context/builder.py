"""ContextBuilder — único caminho por onde um agente recebe informação.

Ver docs/architecture/05-contexto-e-evidencias.md.

Estratégias:
  A — contexto integral: entradas declaradas + documento completo atual
  B — recuperação semântica: itens das entradas em lista reduzidos aos top-k mais próximos da
      descrição da tarefa (experimental: só mede a perda por top-k, não a corrige)
  C — contratos estruturados: exatamente os reads do manifesto
  D — híbrida (padrão): C + digests de fases aprovadas + feedback humano
"""

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES
from openupexp.baml_client.types import ContextItem
from openupexp.db.models import HitlRequest, HitlResponse, Run, SourceDocument
from openupexp.domain import artifacts as store
from openupexp.process.manifest import ReadSpec, TaskSpec

Origin = Literal["required", "previous", "digest", "retrieved", "related", "feedback", "document"]

STRATEGY_VERSIONS = {"A": "A-full@1.0", "B": "B-semantic@1.0", "C": "C-contracts@1.0", "D": "D-hybrid@1.0"}
# itens mantidos por entrada em lista na estratégia B
B_TOP_K = 8


class MissingRequiredInput(Exception):
    pass


class PackageItem(BaseModel):
    origin: Origin
    ref: str
    artifact: str | None = None
    version_id: str | None = None
    content: Any
    reason: str


class Coverage(BaseModel):
    required_ids: list[str] = Field(default_factory=list)
    included_ids: list[str] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)
    satisfied: bool = True
    output_missing_ids: list[str] = Field(default_factory=list)


class ContextPackage(BaseModel):
    strategy: str
    task_id: str
    items: list[PackageItem] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)

    # ---- acesso tipado pelos handlers -------------------------------------------------
    def required(self, artifact: str, default: Any = None) -> Any:
        for it in self.items:
            if it.origin == "required" and it.artifact == artifact:
                return it.content
        return default

    def previous(self, artifact: str) -> dict | None:
        for it in self.items:
            if it.origin == "previous" and it.artifact == artifact:
                return it.content
        return None

    def retrieved(self) -> list[PackageItem]:
        return [it for it in self.items if it.origin == "retrieved"]

    def extras(self, retrieved: set[str] | None = None) -> list[ContextItem]:
        """Itens não obrigatórios, entregues à função BAML no parâmetro `contexto`.

        retrieved, quando informado, restringe os trechos recuperados aos dessa chamada.
        """
        out = []
        for it in self.items:
            if it.origin in ("required", "previous"):
                continue
            if retrieved is not None and it.origin == "retrieved" and it.ref not in retrieved:
                continue
            conteudo = it.content if isinstance(it.content, str) else json.dumps(
                it.content, ensure_ascii=False, indent=1)
            out.append(ContextItem(origem=it.origin, referencia=it.ref, conteudo=conteudo))
        return out

    def dependencies(self) -> dict[uuid.UUID, str]:
        deps: dict[uuid.UUID, str] = {}
        for it in self.items:
            if it.version_id and it.origin in ("required", "digest"):
                deps[uuid.UUID(it.version_id)] = it.artifact or it.origin
        return deps

    def add(self, item: PackageItem) -> None:
        self.items.append(item)

    # ---- persistência ------------------------------------------------------------------
    def canonical(self) -> list[dict]:
        return [it.model_dump(mode="json") for it in self.items]

    def sha256(self) -> str:
        raw = json.dumps(self.canonical(), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def token_estimate(self) -> int:
        return len(json.dumps(self.canonical(), ensure_ascii=False, default=str)) // 4


async def _read_item(
    session: AsyncSession, run: Run, read: ReadSpec
) -> PackageItem | None:
    if read.artifact == "project.scope_document":
        doc = await session.get(SourceDocument, run.scope_document_id) if run.scope_document_id else None
        if doc is None:
            return None
        return PackageItem(
            origin="required", ref=f"source_document:{doc.id}", artifact=read.artifact,
            content=doc.texto or "", reason="entrada declarada no manifesto (documento de escopo)",
        )
    version = await store.lineage_version(session, run, read.artifact)
    if version is None:
        return None
    return PackageItem(
        origin="required", ref=f"artifact_version:{version.id}", artifact=read.artifact,
        version_id=str(version.id), content=version.content,
        reason=f"entrada declarada no manifesto (select={read.select}, v{version.version_no})",
    )


CONSENSUS_POSITIONS = ("concordo", "ressalvas", "objecao")


async def _feedback_items(session: AsyncSession, run: Run) -> list[PackageItem]:
    """Retornos (revisit) decididos pelo humano, com as posições do consenso, se houver."""
    rows = await session.execute(
        select(HitlResponse, HitlRequest)
        .join(HitlRequest, HitlResponse.hitl_request_id == HitlRequest.id)
        .where(HitlRequest.run_id == run.id)
        .order_by(HitlResponse.created_at)
    )
    by_request: dict = {}
    for resp, req in rows.all():
        by_request.setdefault(req.id, (req, []))[1].append(resp)
    out = []
    for req, responses in by_request.values():
        positions = [r for r in responses if r.decision in CONSENSUS_POSITIONS]
        for resp in responses:
            if not resp.decision.startswith("revisit"):
                continue
            partes = [f"Decisão: {resp.decision} (iteração {req.iteracao})"]
            if resp.comentario:
                partes.append(f"Comentário geral: {resp.comentario}")
            for c in resp.item_comments or []:
                partes.append(f"Sobre {c.get('alvo')}: {c.get('texto')}")
            for p in positions:
                if p.comentario or p.item_comments:
                    partes.append(f"Posição de participante no consenso ({p.decision}): {p.comentario or ''}".rstrip())
                    for c in p.item_comments or []:
                        partes.append(f"  sobre {c.get('alvo')}: {c.get('texto')}")
            out.append(PackageItem(
                origin="feedback", ref=f"hitl_response:{resp.id}", content="\n".join(partes),
                reason="feedback do revisor humano em iteração anterior",
            ))
    return out


async def _digest_items(session: AsyncSession, run: Run) -> list[PackageItem]:
    out = []
    for base_id in await store.lineage(session, run):
        for atype, version in (await store.current_versions(session, base_id)).items():
            if atype.startswith("digest.") and version.status == "approved":
                out.append(PackageItem(
                    origin="digest", ref=f"artifact_version:{version.id}", artifact=atype,
                    version_id=str(version.id), content=version.content.get("resumo", ""),
                    reason="digest de fase aprovada (contexto auxiliar)",
                ))
    return out


def task_query(task: TaskSpec) -> str:
    """Descrição da tarefa usada como consulta na estratégia B."""
    return " ".join(x for x in [task.name, task.baml_function, task.theory_ref] if x)


def semantic_select(item: PackageItem, query: str, embedder, k: int | None = None) -> PackageItem:
    """Estratégia B: mantém só os k itens da lista mais próximos da consulta, na ordem original."""
    k = k or B_TOP_K
    at = ARTIFACT_TYPES.get(item.artifact or "")
    if not (at and at.list_field and isinstance(item.content, dict)):
        return item
    rows = list(item.content.get(at.list_field) or [])
    if len(rows) <= k:
        return item
    texts = [json.dumps(r, ensure_ascii=False)[:2000] for r in rows]
    q = embedder.encode_query(query)
    scored = []
    for i, v in enumerate(embedder.encode_passages(texts)):
        dot = sum(a * b for a, b in zip(q, v))
        norm = (sum(a * a for a in q) ** 0.5) * (sum(b * b for b in v) ** 0.5)
        scored.append((dot / norm if norm else 0.0, i))
    keep = sorted(i for _, i in sorted(scored, reverse=True)[:k])
    content = {**item.content, at.list_field: [rows[i] for i in keep]}
    return item.model_copy(update={"content": content,
                                   "reason": f"{item.reason}; estratégia B: top-{k} de {len(rows)} por similaridade"})


def _included(item: PackageItem) -> list[str]:
    at = ARTIFACT_TYPES.get(item.artifact or "")
    if not (at and at.list_field and isinstance(item.content, dict)):
        return []
    return [r.get("id") for r in item.content.get(at.list_field, []) if r.get("id")]


async def derive_package(session: AsyncSession, run: Run, task: TaskSpec, original: ContextPackage,
                         strategy: str, embedder=None) -> tuple[ContextPackage, dict]:
    """Pacote de outra estratégia a partir do pacote original de uma tarefa (laboratório, cap. 14).

    As entradas declaradas e as versões anteriores vêm do pacote original (mesmas versões que a
    tarefa recebeu). Digests e documento integral são os atuais da execução — informado em `notas`.
    """
    if strategy not in STRATEGY_VERSIONS:
        raise ValueError(f"estratégia desconhecida: {strategy}")
    base = [it for it in original.items if it.origin in ("required", "previous")]
    feedback = [it for it in original.items if it.origin == "feedback"]
    notes: dict = {"estado_atual": []}
    if strategy == "B":
        if embedder is None:
            raise ValueError("a estratégia B precisa de um embedder")
        query = task_query(task)
        base = [semantic_select(it, query, embedder) if it.origin == "required" else it for it in base]
    items = base + (feedback if strategy in ("A", "C", "D") else [])
    if strategy == "D":
        digests = [it for it in original.items if it.origin == "digest"] or await _digest_items(session, run)
        if not any(it.origin == "digest" for it in original.items):
            notes["estado_atual"].append("digests")
        items += digests
    if strategy == "A":
        from openupexp.exports.documents import render_current_document

        items.append(PackageItem(origin="document", ref=f"run:{run.id}:documento",
                                 content=await render_current_document(session, run),
                                 reason="estratégia A: documento integral atual"))
        notes["estado_atual"].append("documento")
    required_ids = list(original.coverage.required_ids)
    included = {i for it in items if it.origin == "required" for i in _included(it)}
    coverage = Coverage(required_ids=required_ids, included_ids=[i for i in required_ids if i in included])
    coverage.missing_ids = sorted(set(required_ids) - included)
    coverage.satisfied = not coverage.missing_ids
    return ContextPackage(strategy=STRATEGY_VERSIONS[strategy], task_id=task.id, items=items,
                          coverage=coverage), notes


async def build_context(
    session: AsyncSession, run: Run, task: TaskSpec, strategy: str | None = None, embedder=None
) -> ContextPackage:
    strategy = strategy or run.context_strategy
    if strategy not in STRATEGY_VERSIONS:
        raise ValueError(f"estratégia desconhecida: {strategy}")

    pkg = ContextPackage(strategy=STRATEGY_VERSIONS[strategy], task_id=task.id)
    coverage = Coverage()

    for read in task.reads:
        item = await _read_item(session, run, read)
        if item is None:
            if read.required:
                raise MissingRequiredInput(f"tarefa {task.id}: entrada obrigatória ausente: {read.artifact}")
            continue
        if strategy == "B" and embedder is not None:
            # experimental: a perda por top-k fica registrada em coverage.missing_ids, sem correção
            item = semantic_select(item, task_query(task), embedder)
        pkg.add(item)
        at = ARTIFACT_TYPES.get(read.artifact)
        if read.select == "all_items" and at and at.list_field and item.version_id:
            expected = list((await store.items_of(session, uuid.UUID(item.version_id))).keys())
            delivered = [i.get("id") for i in item.content.get(at.list_field, [])]
            coverage.required_ids += expected
            coverage.included_ids += [k for k in delivered if k in expected]

    # versões anteriores dos próprios artefatos (preservação de IDs em revisões)
    for write in task.writes:
        prev = await store.current_version(session, run.id, write.artifact)
        if prev is not None:
            pkg.add(PackageItem(
                origin="previous", ref=f"artifact_version:{prev.id}", artifact=write.artifact,
                version_id=str(prev.id), content=prev.content,
                reason="versão anterior do artefato produzido (preservação de IDs)",
            ))

    if strategy in ("B", "C", "D", "A"):
        for fb in await _feedback_items(session, run):
            pkg.add(fb)
    if strategy == "D":
        for dg in await _digest_items(session, run):
            pkg.add(dg)
    if strategy == "A":
        from openupexp.exports.documents import render_current_document

        doc = await render_current_document(session, run)
        pkg.add(PackageItem(origin="document", ref=f"run:{run.id}:documento", content=doc,
                            reason="estratégia A: documento integral atual"))

    coverage.missing_ids = sorted(set(coverage.required_ids) - set(coverage.included_ids))
    coverage.satisfied = not coverage.missing_ids
    pkg.coverage = coverage
    return pkg
