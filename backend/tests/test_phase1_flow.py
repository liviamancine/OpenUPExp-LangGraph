"""Fluxo completo da Fase 1 com gateway simulado: HITL, revisit, idempotência, exportação."""

from pathlib import Path

from sqlalchemy import func, select

from openupexp.db.models import (
    Artifact,
    ArtifactVersion,
    ContextPackageRow,
    Evidence,
    Export,
    HitlRequest,
    LlmCall,
    Run,
    TaskExecution,
)
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.retrieval.embeddings import HashEmbedder
from openupexp.retrieval.ingest import add_source, build_corpus_version
from openupexp.worker_main import drain, run_graph


async def _setup(scope_bytes, law_bytes, strategy="D"):
    async with session_scope() as s:
        p = await services.create_project(s, "Fluxo", None, None, None)
        await add_source(s, p.id, "escopo.txt", scope_bytes, "escopo")
        await add_source(s, p.id, "lei_13709_lgpd.txt", law_bytes, "lei")
        await build_corpus_version(s, p.id, HashEmbedder())
        run = await services.start_run(s, p.id, context_strategy=strategy, agent_gateway="fake")
        return run.id


async def _open_request(run_id):
    async with session_scope() as s:
        return await s.scalar(select(HitlRequest).where(HitlRequest.run_id == run_id, HitlRequest.status == "open"))


async def _status(run_id):
    async with session_scope() as s:
        return (await s.get(Run, run_id)).status


async def test_full_phase1_with_revisit_and_approval(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()
    assert await _status(run_id) == "waiting_human"
    req = await _open_request(run_id)
    assert req.task_id == "1.3.gate" and req.iteracao == 1

    # versões entram em revisão
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        assert cur["vision.stakeholders"].status == "in_review"
        stk_v1 = cur["vision.stakeholders"].id
        evidences = (await s.scalars(select(Evidence))).all()
        assert evidences and all(e.verification == "verified" for e in evidences)

    # comentário obrigatório no retorno
    async with session_scope() as s:
        try:
            await services.decide(s, req.id, None, "revisit_1_1", "", bypass_role_check=True)
            raise AssertionError("deveria exigir comentário")
        except services.DomainError as e:
            assert e.status == 422

    async with session_scope() as s:
        await services.decide(s, req.id, None, "revisit_1_1", "Faltou um stakeholder", bypass_role_check=True)
    await drain()
    assert await _status(run_id) == "waiting_human"
    req2 = await _open_request(run_id)
    assert req2.id != req.id and req2.iteracao == 2

    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        stk = cur["vision.stakeholders"]
        assert stk.version_no == 2 and stk.supersedes_id == stk_v1
        # IDs preservados entre iterações
        assert [i["id"] for i in stk.content["stakeholders"]] == \
               [i["id"] for i in (await s.get(ArtifactVersion, stk_v1)).content["stakeholders"]]
        # feedback humano entregue no contexto da reexecução
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "1.1.2",
                                                        TaskExecution.iteracao == 2))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        feedback = [i for i in pkg.items if i["origin"] == "feedback"]
        assert feedback and "Faltou um stakeholder" in feedback[0]["content"]
        assert [i for i in pkg.items if i["origin"] == "previous"]

    async with session_scope() as s:
        await services.decide(s, req2.id, None, "approve", None, bypass_role_check=True)
    await drain()
    assert await _status(run_id) == "completed"

    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        phase_types = {"vision.problem", "vision.stakeholders", "vision.stakeholder_needs", "glossary",
                       "vision.explainability_needs", "vision.positioning", "vision.complementary_requirements",
                       "vision.limits", "vision.domain_terms", "vision.reference_queries"}
        assert {t: v.status for t, v in cur.items() if t in phase_types} == {t: "approved" for t in phase_types}
        assert cur["vision.draft"].origin == "consolidation" and cur["vision.draft"].status == "approved"
        digest = cur["digest.vision"].content
        assert digest["ids_faltantes"] == []
        exp = await s.scalar(select(Export).where(Export.run_id == run_id))
        text = Path(exp.storage_path).read_text(encoding="utf-8")
        assert "# Documento de Visão" in text and "aprovado" in text and "\\n" not in text
        n_calls = await s.scalar(select(func.count(LlmCall.id)).where(LlmCall.run_id == run_id))
        assert n_calls >= 20


async def test_gate_is_idempotent_on_reexecution(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()
    # retomada sem decisão reexecuta o nó do gateway: não pode duplicar efeitos
    await run_graph(run_id, "retry")
    await run_graph(run_id, "retry")
    async with session_scope() as s:
        n_req = await s.scalar(select(func.count(HitlRequest.id)).where(HitlRequest.run_id == run_id))
        n_wait = await s.scalar(select(func.count(TaskExecution.id)).where(
            TaskExecution.run_id == run_id, TaskExecution.task_id == "1.3.gate"))
        assert n_req == 1 and n_wait == 1
        assert (await s.get(Run, run_id)).status == "waiting_human"


async def test_approval_with_stale_is_allowed_and_recorded(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()
    req = await _open_request(run_id)
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        cur["vision.limits"].status = "stale"
    async with session_scope() as s:
        await services.decide(s, req.id, None, "approve", None, bypass_role_check=True)
    async with session_scope() as s:
        decided = await s.get(HitlRequest, req.id)
        assert decided.status == "decided"
        assert decided.payload["aprovado_com_desatualizadas"] == ["vision.limits"]
    await drain()
    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"


async def test_human_edit_updates_stale_version(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()
    async with session_scope() as s:
        v = await store.current_version(s, run_id, "vision.stakeholders")
        v.status = "stale"
    async with session_scope() as s:
        v = await store.current_version(s, run_id, "vision.stakeholders")
        content = dict(v.content)
        content["stakeholders"] = [dict(i) for i in content["stakeholders"]]
        content["stakeholders"][0]["responsabilidade"] = "Conferida pelo engenheiro"
        edited = await services.human_edit(s, v.id, content, None, bypass_role_check=True)
        assert edited.status == "in_review" and edited.origin == "human_edit"


async def test_human_edit_creates_version_and_is_used_on_approval(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()
    async with session_scope() as s:
        v = await store.current_version(s, run_id, "vision.stakeholders")
        content = dict(v.content)
        content["stakeholders"] = [dict(i) for i in content["stakeholders"]]
        content["stakeholders"][0]["responsabilidade"] = "Responsabilidade definida pelo engenheiro"
        edited = await services.human_edit(s, v.id, content, None, bypass_role_check=True)
        assert edited.origin == "human_edit" and edited.status == "in_review"
        first = edited.content["stakeholders"][0]
        assert all(g["campo"] != "responsabilidade" for g in first["lacunas"])  # lacuna preenchida sai
        positioning = await store.current_version(s, run_id, "vision.positioning")
        assert positioning.status == "in_review"  # edição humana não invalida dependentes
    req = await _open_request(run_id)
    async with session_scope() as s:
        await services.decide(s, req.id, None, "approve", None, bypass_role_check=True)
    await drain()
    async with session_scope() as s:
        draft = await store.current_version(s, run_id, "vision.draft")
        assert "Responsabilidade definida pelo engenheiro" in draft.content["markdown"]


async def test_strategy_a_includes_full_document(scope_bytes, law_bytes):
    run_id = await _setup(scope_bytes, law_bytes, strategy="A")
    await drain()
    async with session_scope() as s:
        rows = (await s.execute(
            select(TaskExecution.task_id, ContextPackageRow.items, ContextPackageRow.strategy)
            .join(ContextPackageRow, ContextPackageRow.task_execution_id == TaskExecution.id)
            .where(TaskExecution.run_id == run_id))).all()
        assert rows and all(st.startswith("A-") for _, _, st in rows)
        assert all(any(i["origin"] == "document" for i in items) for _, items, _ in rows)


async def test_artifacts_are_scoped_by_run(scope_bytes, law_bytes):
    r1 = await _setup(scope_bytes, law_bytes)
    await drain()
    async with session_scope() as s:
        n = await s.scalar(select(func.count(Artifact.id)).where(Artifact.run_id == r1))
        assert n >= 10
