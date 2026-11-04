"""Serviços de aplicação usados pela API e pela CLI (sem HTTP, sem LLM)."""

import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES, items_from_content
from openupexp.config import get_settings
from openupexp.db.models import (
    ArtifactVersion,
    HitlRequest,
    HitlResponse,
    ProcessManifest,
    Project,
    ProjectMember,
    Run,
)
from openupexp.domain import artifacts as store
from openupexp.domain.events import audit, emit
from openupexp.llm.catalog import resolve_profile
from openupexp.observability.llm import baml_src_sha
from openupexp.process.manifest import bpmn_source_commit, get_manifest
from openupexp.queue.jobs import enqueue
from openupexp.retrieval.ingest import latest_corpus_version, latest_scope_document

DECIDER_ROLES = {"requirements_engineer"}
# Versões que o Engenheiro pode editar; "stale" inclusive, pois a edição é como ele as atualiza.
EDITABLE_STATUSES = ("draft", "in_review", "stale")
CONSENSUS_POSITIONS = ("concordo", "ressalvas", "objecao")


class DomainError(Exception):
    """Erro de regra de negócio (mapeado para 4xx na API)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


async def ensure_manifest(session: AsyncSession) -> ProcessManifest:
    manifest = get_manifest()
    row = await session.get(ProcessManifest, manifest.manifest_version)
    if row is None:
        row = ProcessManifest(
            version=manifest.manifest_version, bpmn_commit=bpmn_source_commit(),
            conteudo=manifest.model_dump(mode="json"), sha256=manifest.sha256(),
        )
        session.add(row)
        await session.flush()
    elif row.sha256 != manifest.sha256():
        raise DomainError(
            f"O manifesto {manifest.manifest_version} mudou sem incremento de versão; "
            "incremente manifest_version para preservar a reprodutibilidade.", 409)
    return row


async def member_role(session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    m = await session.get(ProjectMember, (project_id, user_id))
    return m.papel_plataforma if m else None


async def create_project(session: AsyncSession, nome: str, dominio: str | None, descricao: str | None,
                         owner_id: uuid.UUID | None) -> Project:
    p = Project(nome=nome, dominio=dominio, descricao=descricao, created_by=owner_id)
    session.add(p)
    await session.flush()
    if owner_id:
        session.add(ProjectMember(project_id=p.id, user_id=owner_id, papel_plataforma="requirements_engineer",
                                  papel_openupexp="Engenheiro de Requisitos"))
    await audit(session, "user", str(owner_id) if owner_id else None, "create", "project", str(p.id))
    return p


async def start_run(
    session: AsyncSession,
    project_id: uuid.UUID,
    phase: str = "1",
    context_strategy: str = "D",
    agent_gateway: str | None = None,
    model_profile: dict | None = None,
    user_id: uuid.UUID | None = None,
    experiment_id: uuid.UUID | None = None,
    base_run_id: uuid.UUID | None = None,
    llm_profile_id: uuid.UUID | None = None,
) -> Run:
    manifest = get_manifest()
    spec = manifest.phase(phase)
    if not spec.implemented:
        raise DomainError(f"Fase {phase} ainda não é executável.", 422)
    if spec.requires_phase:
        await _check_base_run(session, project_id, spec.requires_phase, base_run_id)
    elif base_run_id:
        raise DomainError(f"A Fase {phase} não parte de outra execução.", 422)
    if context_strategy not in ("A", "B", "C", "D"):
        raise DomainError("Estratégias disponíveis: A, B (experimental), C, D.", 422)
    await ensure_manifest(session)
    scope = await latest_scope_document(session, project_id)
    if scope is None:
        raise DomainError("O projeto não tem documento de escopo (source_kind=escopo).", 422)
    corpus = await latest_corpus_version(session, project_id)
    gateway = agent_gateway or get_settings().agent_gateway
    if gateway == "baml" and not model_profile:
        # snapshot do perfil escolhido (ou do padrão) congelado na execução — cap. 14
        try:
            model_profile = await resolve_profile(session, llm_profile_id)
        except LookupError as exc:
            raise DomainError(str(exc), 422) from exc

    run_id = uuid.uuid4()
    run = Run(
        id=run_id, project_id=project_id, manifest_version=manifest.manifest_version,
        corpus_version_id=corpus.id if corpus else None, scope_document_id=scope.id, phase=phase,
        context_strategy=context_strategy, model_profile=model_profile or {},
        agent_gateway=gateway, baml_src_sha=baml_src_sha(),
        thread_id=f"run-{run_id}", status="queued", created_by=user_id, experiment_id=experiment_id,
        base_run_id=base_run_id,
    )
    session.add(run)
    await session.flush()
    await enqueue(session, "run.start", {"run_id": str(run.id)}, run_id=run.id)
    await emit(session, run.id, "run_queued", phase=phase, strategy=context_strategy)
    await audit(session, "user", str(user_id) if user_id else None, "start_run", "run", str(run.id))
    return run


async def _check_base_run(session: AsyncSession, project_id: uuid.UUID, phase: str,
                          base_run_id: uuid.UUID | None) -> None:
    from openupexp.agents.registry import PHASE_DOCUMENT

    base = await session.get(Run, base_run_id) if base_run_id else None
    if base is None or base.project_id != project_id or base.phase != phase:
        raise DomainError(f"Escolha uma execução da Fase {phase} deste projeto como base.", 422)
    doc = await store.current_version(session, base.id, PHASE_DOCUMENT[phase])
    if base.status != "completed" or doc is None or doc.status != "approved":
        raise DomainError(f"A execução de base precisa estar concluída, com a Fase {phase} aprovada.", 422)


async def retry_run(session: AsyncSession, run: Run, user_id: uuid.UUID | None = None) -> None:
    if run.status != "failed":
        raise DomainError("Só execuções com falha podem ser retomadas.", 409)
    run.status = "queued"
    run.error = None
    await enqueue(session, "run.retry", {"run_id": str(run.id)}, run_id=run.id)
    await emit(session, run.id, "run_queued", retry=True)
    await audit(session, "user", str(user_id) if user_id else None, "retry_run", "run", str(run.id))


async def decide(
    session: AsyncSession,
    request_id: uuid.UUID,
    user_id: uuid.UUID | None,
    decision: str,
    comentario: str | None = None,
    item_comments: list[dict] | None = None,
    bypass_role_check: bool = False,
) -> HitlResponse:
    """Registra a decisão do Engenheiro (aprovação, entrada ou encerramento de consenso) e retoma o grafo."""
    req = await session.get(HitlRequest, request_id, with_for_update=True)
    if req is None:
        raise DomainError("Solicitação inexistente.", 404)
    if req.status != "open":
        raise DomainError("Esta solicitação já foi decidida.", 409)
    run = await session.get(Run, req.run_id)
    if not bypass_role_check:
        role = await member_role(session, run.project_id, user_id) if user_id else None
        if role not in DECIDER_ROLES:
            raise DomainError("Apenas o Engenheiro de Requisitos do projeto decide este gateway.", 403)

    outcomes = req.payload.get("outcomes", {})
    if decision not in outcomes:
        raise DomainError(f"Decisão inválida. Opções: {sorted(outcomes)}", 422)
    if outcomes[decision].get("comment_required") and not (comentario or "").strip():
        raise DomainError("Comentário obrigatório para esta decisão.", 422)
    if req.kind == "input" and decision == "submit":
        from openupexp.db.models import SourceDocument
        from openupexp.retrieval.ingest import ELICITATION_KINDS

        n = await session.scalar(select(func.count(SourceDocument.id)).where(
            SourceDocument.project_id == run.project_id, SourceDocument.ativo.is_(True),
            SourceDocument.source_kind.in_(ELICITATION_KINDS)))
        if not n:
            raise DomainError("Envie ao menos um documento de elicitação ou prossiga sem material, justificando.", 422)
    stale: list[str] = []
    if decision == "approve":
        # Sem retorno à IA: o Engenheiro confere e edita as partes desatualizadas e aprova assim mesmo.
        # Quais estavam desatualizadas fica registrado na solicitação e na auditoria.
        stale = [t for t, v in (await store.current_versions(session, run.id)).items()
                 if v.status == "stale" and t in ARTIFACT_TYPES]
        if stale:
            req.payload = {**req.payload, "aprovado_com_desatualizadas": stale}
    if req.kind == "consensus" and decision == "close":
        tally = await consensus_tally(session, req.id)
        if (tally["objecao"] or not tally["participantes"]) and not (comentario or "").strip():
            raise DomainError("Há objeções bloqueantes (ou nenhuma posição registrada): "
                              "justifique o encerramento no comentário.", 422)
        req.payload = {**req.payload, "fechamento": {
            "objecoes": tally["objecao"], "ressalvas": tally["ressalvas"], "concordancias": tally["concordo"],
            "override": bool(tally["objecao"] or not tally["participantes"])}}

    resp = HitlResponse(hitl_request_id=req.id, user_id=user_id, decision=decision, comentario=comentario,
                        item_comments=item_comments or [], round=req.round)
    session.add(resp)
    req.status = "decided"
    req.decided_at = datetime.now(timezone.utc)
    await session.flush()
    await enqueue(session, "run.resume", {"run_id": str(run.id), "resume": {
        "decision": decision, "comentario": comentario, "response_id": str(resp.id)}}, run_id=run.id)
    await emit(session, run.id, "hitl_decided", hitl_request_id=req.id, decision=decision)
    await audit(session, "user", str(user_id) if user_id else None, "decide", "hitl_request", str(req.id),
                decision=decision, comentario=comentario, desatualizadas=stale)
    return resp


async def consensus_tally(session: AsyncSession, request_id: uuid.UUID) -> dict:
    """Última posição de cada participante numa rodada de consenso."""
    rows = (await session.scalars(
        select(HitlResponse).where(HitlResponse.hitl_request_id == request_id,
                                   HitlResponse.decision.in_(CONSENSUS_POSITIONS))
        .order_by(HitlResponse.created_at))).all()
    latest = {r.user_id: r.decision for r in rows}
    counts = {p: sum(1 for v in latest.values() if v == p) for p in CONSENSUS_POSITIONS}
    return {**counts, "participantes": len(latest)}


async def record_position(
    session: AsyncSession,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    posicao: str,
    comentario: str | None = None,
    item_comments: list[dict] | None = None,
    role: str | None = None,
) -> HitlResponse:
    """Posição de um participante no consenso (não retoma o grafo; o Engenheiro encerra a rodada)."""
    req = await session.get(HitlRequest, request_id)
    if req is None or req.kind != "consensus":
        raise DomainError("Rodada de consenso inexistente.", 404)
    if req.status != "open":
        raise DomainError("Esta rodada de consenso já foi encerrada.", 409)
    if posicao not in CONSENSUS_POSITIONS:
        raise DomainError(f"Posição inválida. Opções: {list(CONSENSUS_POSITIONS)}", 422)
    allowed = (req.policy or {}).get("participant_roles") or []
    if role != "admin" and role not in allowed:
        raise DomainError("Seu papel no projeto não participa deste consenso.", 403)
    if posicao != "concordo" and not (comentario or "").strip() and not item_comments:
        raise DomainError("Explique a ressalva ou a objeção no comentário.", 422)
    resp = HitlResponse(hitl_request_id=req.id, user_id=user_id, decision=posicao, comentario=comentario,
                        item_comments=item_comments or [], round=req.round)
    session.add(resp)
    await session.flush()
    await emit(session, req.run_id, "consensus_position", hitl_request_id=req.id, posicao=posicao)
    await audit(session, "user", str(user_id), "consensus_position", "hitl_request", str(req.id),
                posicao=posicao, comentario=comentario)
    return resp


async def human_edit(
    session: AsyncSession, version_id: uuid.UUID, content: dict, user_id: uuid.UUID | None,
    bypass_role_check: bool = False,
) -> ArtifactVersion:
    """Edição humana de um artefato em revisão: gera nova versão origin=human_edit."""
    base = await session.get(ArtifactVersion, version_id)
    if base is None:
        raise DomainError("Versão inexistente.", 404)
    from openupexp.db.models import Artifact

    artifact = await session.get(Artifact, base.artifact_id)
    current = await store.current_version(session, artifact.run_id, artifact.artifact_type)
    if current.id != base.id:
        raise DomainError("Edição baseada em versão desatualizada; recarregue o artefato.", 409)
    if base.status not in EDITABLE_STATUSES:
        raise DomainError(f"Versões com status '{base.status}' não podem ser editadas.", 409)
    run = await session.get(Run, artifact.run_id)
    if not bypass_role_check:
        role = await member_role(session, run.project_id, user_id) if user_id else None
        if role not in DECIDER_ROLES:
            raise DomainError("Apenas o Engenheiro de Requisitos edita artefatos.", 403)

    at = ARTIFACT_TYPES.get(artifact.artifact_type)
    if at is None or at.schema is None:
        raise DomainError("Este artefato é derivado e não pode ser editado diretamente.", 422)
    try:
        validated = at.schema.model_validate(content).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError(f"Conteúdo inválido para {at.schema.__name__}: {exc.errors()[:3]}", 422) from exc
    # campos extras do sistema (ex.: fundamentacao_verificada, alerta) são preservados por item
    if at.list_field:
        old = {i.get("id"): i for i in base.content.get(at.list_field, [])}
        for item in validated.get(at.list_field, []):
            extra = {k: v for k, v in old.get(item.get("id"), {}).items() if k not in item}
            item.update(extra)
        for item in validated.get(at.list_field, []):
            _drop_filled_gaps(item)
        keys = [i.get("id") for i in validated.get(at.list_field, [])]
        if any(not k for k in keys) or len(set(keys)) != len(keys):
            raise DomainError(f"Cada item precisa de um ID único com prefixo {at.prefix}-.", 422)

    _drop_filled_gaps(validated)
    # campos de sistema fora do contrato (ex.: cobertura de pares em 3.2.3) são preservados
    for key, value in base.content.items():
        validated.setdefault(key, value)
    deps = await session.execute(
        select(store.ArtifactDependency.depends_on_version_id, store.ArtifactDependency.via_read)
        .where(store.ArtifactDependency.version_id == base.id)
    )
    version = await store.save_version(
        session, project_id=run.project_id, run_id=run.id, phase=artifact.phase,
        artifact_type=artifact.artifact_type, content=validated, origin="human_edit",
        items=items_from_content(artifact.artifact_type, validated),
        schema_name=at.schema.__name__, schema_sha=store.schema_hash(at.schema),
        depends_on={d: v for d, v in deps.all()}, created_by_user=user_id,
        # editar uma versão desatualizada é como o Engenheiro a atualiza (não há retorno à IA)
        status="in_review" if base.status == "stale" else base.status, iteracao=base.iteracao, invalidate=False,
    )
    # O rascunho (1.2.4) não é invalidado: a consolidação (1.3.2) remonta o documento
    # a partir das versões mais recentes, incluindo as edições humanas.
    await emit(session, run.id, "artifact_edited", artifact=artifact.artifact_type, version_id=version.id,
               version_no=version.version_no)
    await audit(session, "user", str(user_id) if user_id else None, "edit", "artifact_version",
                str(version.id), base=str(base.id))
    return version


def _drop_filled_gaps(obj: dict) -> None:
    """Remove lacunas cujo campo o revisor humano preencheu."""
    lacunas = obj.get("lacunas")
    if isinstance(lacunas, list):
        obj["lacunas"] = [g for g in lacunas if obj.get(g.get("campo")) in (None, "", [])]
    if obj.get("lacuna") and obj.get("resposta"):
        obj["lacuna"] = None


async def run_counts(session: AsyncSession, run_id: uuid.UUID) -> dict:
    from openupexp.db.models import LlmCall

    row = (await session.execute(
        select(func.count(LlmCall.id), func.coalesce(func.sum(LlmCall.input_tokens), 0),
               func.coalesce(func.sum(LlmCall.output_tokens), 0), func.coalesce(func.sum(LlmCall.latency_ms), 0),
               func.sum(LlmCall.custo_usd))
        .where(LlmCall.run_id == run_id)
    )).one()
    return {"llm_calls": row[0], "input_tokens": int(row[1]), "output_tokens": int(row[2]),
            "latency_ms": int(row[3]), "custo_usd": float(row[4]) if row[4] is not None else None}
