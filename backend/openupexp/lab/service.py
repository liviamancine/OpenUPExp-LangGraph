"""Laboratório de modelos (cap. 14 §14.5): a mesma tarefa, com o mesmo pacote de contexto, em vários modelos.

Cada tentativa reexecuta o handler da tarefa com:
- o pacote de contexto guardado na execução original, sem os trechos recuperados e itens
  relacionados (que o próprio handler acrescenta durante a execução);
- um gateway próprio, que não grava chamadas na execução original;
- uma sessão de banco somente para leitura (rollback no fim): nada é persistido em artefatos.

A recuperação é refeita pelo handler sobre a mesma versão do corpus e o mesmo embedder; a
tentativa registra se os trechos recuperados coincidiram com os da execução original.
"""

import json
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES
from openupexp.agents.runtime import TaskContext, WriteResult
from openupexp.context.builder import ContextPackage
from openupexp.db.models import (
    Artifact,
    ArtifactVersion,
    ContextPackageRow,
    CorpusVersion,
    Evidence,
    InferenceProfile,
    LabComparison,
    LabRating,
    LabTrial,
    LlmCall,
    LlmModel,
    Run,
    TaskExecution,
)
from openupexp.db.session import session_scope, sessionmaker
from openupexp.llm.catalog import snapshot_of, usable
from openupexp.observability.llm import baml_src_sha
from openupexp.process.manifest import get_manifest
from openupexp.queue.jobs import enqueue
from openupexp.retrieval.embeddings import get_embedder

FAKE = "fake"
FAKE_SNAPSHOT = {"provider": FAKE, "profile_slug": FAKE, "profile_nome": "Modo de teste (simulado)", "model": "fake"}
# origens que o handler acrescenta ao pacote durante a execução
RUNTIME_ORIGINS = ("retrieved", "related")


class LabError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _handlers() -> dict:
    from openupexp.agents.graph import HANDLERS

    return HANDLERS


# ---------------------------------------------------------------------------
# Gateway do laboratório: chama o modelo e acumula métricas na tentativa
# ---------------------------------------------------------------------------


class LabGateway:
    name = "lab"

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        self.calls: list[dict] = []

    async def call(self, function, entrada, contexto, *, run_id=None, task_execution_id=None):
        started = time.perf_counter()
        record: dict = {"function": function}
        try:
            if self.snapshot.get("provider") == FAKE:
                from openupexp.agents import fake

                result = getattr(fake, function)(entrada, contexto)
                prompt = len(entrada.model_dump_json()) + sum(len(c.conteudo) for c in contexto)
                record.update(input_tokens=prompt // 4,
                              output_tokens=len(json.dumps(result.model_dump(), ensure_ascii=False)) // 4)
            else:
                from baml_py import Collector

                from openupexp.agents.gateway import BamlGateway
                from openupexp.baml_client.async_client import b

                collector = Collector(name=f"lab:{function}")
                result = await getattr(b, function)(entrada, contexto,
                                                    baml_options=BamlGateway(self.snapshot)._options(collector))
                usage = collector.last.usage if collector.last else None
                record.update(input_tokens=getattr(usage, "input_tokens", None),
                              output_tokens=getattr(usage, "output_tokens", None))
            record["status"] = "ok"
            return result
        except Exception as exc:
            record.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:500]}")
            raise
        finally:
            record["latency_ms"] = int((time.perf_counter() - started) * 1000)
            self.calls.append(record)


# ---------------------------------------------------------------------------
# Métricas comuns (tentativas e execução original)
# ---------------------------------------------------------------------------


def _count_gaps(value) -> int:
    if isinstance(value, dict):
        n = len(value.get("lacunas") or []) + (1 if value.get("lacuna") else 0)
        return n + sum(_count_gaps(v) for k, v in value.items() if k not in ("lacunas", "lacuna"))
    if isinstance(value, list):
        return sum(_count_gaps(v) for v in value)
    return 0


def _artifact_summary(artifact: str, content: dict) -> dict:
    at = ARTIFACT_TYPES.get(artifact)
    items = content.get(at.list_field) if at and at.list_field else None
    return {"artifact": artifact, "titulo": at.title if at else artifact,
            "itens": len(items) if isinstance(items, list) else None, "lacunas": _count_gaps(content)}


def _call_totals(calls: list[dict]) -> dict:
    return {
        "chamadas": len(calls),
        "chamadas_com_erro": sum(1 for c in calls if c.get("status") != "ok"),
        "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
        "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
        "latency_ms": sum(c.get("latency_ms") or 0 for c in calls),
    }


def _evidence_counts(verifications: list[str]) -> dict:
    return {"total": len(verifications), "verificadas": sum(1 for v in verifications if v == "verified"),
            "nao_verificadas": sum(1 for v in verifications if v != "verified")}


def _retrieved_refs(items) -> list[str]:
    return sorted({(it["ref"] if isinstance(it, dict) else it.ref) for it in items
                   if (it["origin"] if isinstance(it, dict) else it.origin) == "retrieved"})


def _json_safe(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def trial_output(results: list[WriteResult]) -> list[dict]:
    out = []
    for r in results:
        content = dict(r.content)
        at = ARTIFACT_TYPES.get(r.artifact_type)
        if at and at.list_field and r.raw_items is not None:
            content[at.list_field] = r.raw_items
        out.append({"artifact": r.artifact_type, "titulo": at.title if at else r.artifact_type,
                    "content": _json_safe(content)})
    return out


def trial_metrics(results: list[WriteResult], package: ContextPackage, calls: list[dict],
                  original_refs: list[str], duration_ms: int) -> dict:
    output = trial_output(results)
    verifications = [ev.get("verificacao") for r in results for _, ev in r.item_evidences]
    verifications += [ev.verification for r in results for ev in r.evidences]
    refs = _retrieved_refs(package.items)
    arts = [_artifact_summary(o["artifact"], o["content"]) for o in output]
    return {
        "contrato_valido": True,
        "artefatos": arts,
        "itens": sum(a["itens"] or 0 for a in arts),
        "lacunas": sum(a["lacunas"] for a in arts),
        "itens_faltantes": list(package.coverage.output_missing_ids),
        "evidencias": _evidence_counts(verifications),
        "recuperacao": {"identica": refs == original_refs, "trechos": len(refs),
                        "so_na_original": sorted(set(original_refs) - set(refs)),
                        "so_nesta": sorted(set(refs) - set(original_refs))},
        **_call_totals(calls),
        "duracao_ms": duration_ms,
    }


async def reference(session: AsyncSession, comp: LabComparison) -> dict:
    """A execução original, com as mesmas métricas das tentativas, para comparação."""
    te = await session.get(TaskExecution, comp.source_task_execution_id)
    run = await session.get(Run, comp.run_id)
    version_ids = [uuid.UUID(v) for v in (te.meta or {}).get("versions", [])]
    versions = (await session.execute(
        select(ArtifactVersion.content, Artifact.artifact_type).join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
        .where(ArtifactVersion.id.in_(version_ids)))).all() if version_ids else []
    evs = (await session.scalars(select(Evidence).where(Evidence.artifact_version_id.in_(version_ids)))).all() \
        if version_ids else []
    calls = (await session.scalars(select(LlmCall).where(LlmCall.task_execution_id == te.id))).all()
    pkg = await session.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
    call_rows = [{"function": c.baml_function, "status": c.status, "input_tokens": c.input_tokens,
                  "output_tokens": c.output_tokens, "latency_ms": c.latency_ms, "model": c.model} for c in calls]
    arts = [_artifact_summary(atype, content) for content, atype in versions]
    models = sorted({c.model for c in calls if c.model})
    return {
        "nome": "Execução original",
        "modelo": (run.model_profile or {}).get("profile_nome")
        or ("Modo de teste (simulado)" if run.agent_gateway == "fake" else ", ".join(models) or "—"),
        "output": [{"artifact": atype, "titulo": ARTIFACT_TYPES[atype].title if atype in ARTIFACT_TYPES else atype,
                    "content": content} for content, atype in versions],
        "metrics": {
            "contrato_valido": te.status == "completed", "artefatos": arts,
            "itens": sum(a["itens"] or 0 for a in arts), "lacunas": sum(a["lacunas"] for a in arts),
            "itens_faltantes": ((pkg.coverage or {}).get("output_missing_ids") or []) if pkg else [],
            "evidencias": _evidence_counts([e.verification for e in evs]),
            "recuperacao": {"identica": True, "trechos": len(_retrieved_refs(pkg.items)) if pkg else 0,
                            "so_na_original": [], "so_nesta": []},
            **_call_totals(call_rows),
            "duracao_ms": int((te.fim - te.inicio).total_seconds() * 1000) if te.fim and te.inicio else None,
        },
    }


# ---------------------------------------------------------------------------
# Fontes elegíveis e criação de comparações
# ---------------------------------------------------------------------------


async def _source(session: AsyncSession, te_id: uuid.UUID) -> tuple[TaskExecution, Run, ContextPackageRow]:
    te = await session.get(TaskExecution, te_id)
    if te is None:
        raise LabError("Tarefa inexistente.", 404)
    run = await session.get(Run, te.run_id)
    task = get_manifest(run.manifest_version).task(te.task_id)
    if task.mechanism != "agent" or te.task_id not in _handlers():
        raise LabError("Só tarefas executadas pela IA podem ir ao laboratório.")
    if te.status != "completed":
        raise LabError("Escolha uma tarefa concluída.")
    pkg = await session.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
    if pkg is None:
        raise LabError("Esta tarefa não tem pacote de contexto guardado.")
    return te, run, pkg


async def eligible_sources(session: AsyncSession, run_id: uuid.UUID) -> list[dict]:
    run = await session.get(Run, run_id)
    manifest = get_manifest(run.manifest_version)
    handlers = _handlers()
    rows = (await session.execute(
        select(TaskExecution, ContextPackageRow)
        .join(ContextPackageRow, ContextPackageRow.task_execution_id == TaskExecution.id)
        .where(TaskExecution.run_id == run_id, TaskExecution.status == "completed")
        .order_by(TaskExecution.inicio))).all()
    out = []
    for te, pkg in rows:
        try:
            spec = manifest.task(te.task_id)
        except KeyError:
            continue
        if spec.mechanism == "agent" and te.task_id in handlers:
            out.append({"task_execution_id": str(te.id), "task_id": te.task_id, "nome": spec.name,
                        "funcao": spec.baml_function, "iteracao": te.iteracao, "inicio": te.inicio.isoformat(),
                        "tokens_contexto": pkg.token_estimate})
    return out


async def _snapshots(session: AsyncSession, profile_ids: list[str]) -> list[dict]:
    if not profile_ids:
        raise LabError("Escolha ao menos um modelo.")
    if len(profile_ids) > 6:
        raise LabError("Compare no máximo 6 modelos por vez.")
    snaps = []
    for pid in profile_ids:
        if pid == FAKE:
            snaps.append(dict(FAKE_SNAPSHOT))
            continue
        row = (await session.execute(select(InferenceProfile, LlmModel)
                                     .join(LlmModel, LlmModel.id == InferenceProfile.model_id)
                                     .where(InferenceProfile.id == uuid.UUID(pid)))).first()
        if row is None:
            raise LabError("Perfil de modelo inexistente.", 404)
        if not usable(*row):
            raise LabError(f"O perfil '{row[0].nome}' não está disponível.", 409)
        snaps.append(await snapshot_of(*row))
    return snaps


async def create_comparison(session: AsyncSession, te_id: uuid.UUID, profile_ids: list[str],
                            notes: str | None, user_id: uuid.UUID | None) -> LabComparison:
    te, run, pkg = await _source(session, te_id)
    snaps = await _snapshots(session, profile_ids)
    comp = LabComparison(id=uuid.uuid4(), source_task_execution_id=te.id, run_id=run.id, project_id=run.project_id,
                         task_id=te.task_id, baml_src_sha=baml_src_sha(), source_baml_src_sha=run.baml_src_sha,
                         package_sha256=pkg.sha256, notes=notes, created_by=user_id)
    session.add(comp)
    await session.flush()
    for i, snap in enumerate(snaps):
        trial = LabTrial(id=uuid.uuid4(), comparison_id=comp.id, position=i, profile_snapshot=snap,
                         status="queued", output=[], metrics={}, calls=[])
        session.add(trial)
        await session.flush()
        await enqueue(session, "lab.trial", {"trial_id": str(trial.id)})
    return comp


async def cancel_trial(session: AsyncSession, trial_id: uuid.UUID) -> LabTrial:
    trial = await session.get(LabTrial, trial_id)
    if trial is None:
        raise LabError("Tentativa inexistente.", 404)
    if trial.status != "queued":
        raise LabError("Só tentativas ainda na fila podem ser canceladas.", 409)
    trial.status = "cancelled"
    trial.finished_at = datetime.now(UTC)
    return trial


async def rate_trial(session: AsyncSession, trial_id: uuid.UUID, user_id: uuid.UUID, nota: int,
                     comentario: str | None) -> LabRating:
    if not 1 <= nota <= 5:
        raise LabError("A nota vai de 1 a 5.")
    trial = await session.get(LabTrial, trial_id)
    if trial is None or trial.status != "completed":
        raise LabError("Só tentativas concluídas recebem nota.", 409)
    rating = await session.scalar(select(LabRating).where(LabRating.trial_id == trial_id, LabRating.user_id == user_id))
    if rating is None:
        rating = LabRating(id=uuid.uuid4(), trial_id=trial_id, user_id=user_id, nota=nota)
        session.add(rating)
    rating.nota, rating.comentario = nota, comentario
    await session.flush()
    return rating


# ---------------------------------------------------------------------------
# Execução de uma tentativa (job lab.trial no worker)
# ---------------------------------------------------------------------------


async def run_trial(trial_id: uuid.UUID) -> str:
    async with session_scope() as s:
        trial = await s.get(LabTrial, trial_id)
        if trial is None or trial.status != "queued":
            return trial.status if trial else "missing"
        trial.status, trial.started_at = "running", datetime.now(UTC)
        comp = await s.get(LabComparison, trial.comparison_id)
        snapshot, te_id = dict(trial.profile_snapshot), comp.source_task_execution_id

    gateway = LabGateway(snapshot)
    started = time.perf_counter()
    try:
        async with sessionmaker()() as s:
            te, run, pkg_row = await _source(s, te_id)
            manifest = get_manifest(run.manifest_version)
            phase, task = manifest.phase(run.phase), manifest.task(te.task_id)
            package = ContextPackage(strategy=pkg_row.strategy, task_id=te.task_id,
                                     items=[it for it in pkg_row.items if it["origin"] not in RUNTIME_ORIGINS])
            embedder = get_embedder()
            if run.corpus_version_id:
                cv = await s.get(CorpusVersion, run.corpus_version_id)
                embedder = get_embedder(cv.embedding_provider, cv.embedding_model)
            ctx = TaskContext(s, run, phase, task, package, gateway, embedder, te, te.iteracao)
            results = await _handlers()[te.task_id](ctx)
            metrics = trial_metrics(results, package, gateway.calls, _retrieved_refs(pkg_row.items),
                                    int((time.perf_counter() - started) * 1000))
            output = trial_output(results)
            await s.rollback()  # o laboratório não grava nada nos artefatos
        status, error = "completed", None
    except Exception as exc:  # noqa: BLE001 — falha do modelo ou do contrato é resultado da tentativa
        status, error = "failed", f"{type(exc).__name__}: {str(exc)[:1500]}"
        output = []
        metrics = {"contrato_valido": False, **_call_totals(gateway.calls),
                   "duracao_ms": int((time.perf_counter() - started) * 1000)}

    async with session_scope() as s:
        trial = await s.get(LabTrial, trial_id)
        trial.status, trial.error, trial.output, trial.metrics = status, error, output, metrics
        trial.calls, trial.finished_at = gateway.calls, datetime.now(UTC)
    return status
