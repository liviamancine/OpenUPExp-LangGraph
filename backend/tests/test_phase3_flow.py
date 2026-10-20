"""Fluxo completo da Fase 3 (Análise) sobre uma Fase 2 aprovada, com gateway simulado."""

from pathlib import Path

from sqlalchemy import select

from openupexp.db.models import ContextPackageRow, Export, Run, TaskExecution, TraceLink
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.retrieval.ingest import add_source
from openupexp.worker_main import drain

from .test_phase2_flow import ELICITATION_TEXT, _approved_phase1, _expect_error, _open_request


async def _approved_phase2(scope_bytes, law_bytes):
    project_id, base_id, engineer, participant = await _approved_phase1(scope_bytes, law_bytes)
    async with session_scope() as s:
        await add_source(s, project_id, "entrevistas.txt", ELICITATION_TEXT.encode(), "elicitacao")
        run_id = (await services.start_run(s, project_id, phase="2", agent_gateway="fake",
                                           base_run_id=base_id)).id
    await drain()
    for decision in ("submit", "close", "approve"):
        req = await _open_request(run_id)
        async with session_scope() as s:
            if decision == "close":
                await services.record_position(s, req.id, participant, "concordo", role="participant")
            await services.decide(s, req.id, engineer, decision, None)
        await drain()
    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"
    return project_id, base_id, run_id, engineer, participant


async def test_phase3_full_flow(scope_bytes, law_bytes):
    project_id, phase1_id, phase2_id, engineer, participant = await _approved_phase2(scope_bytes, law_bytes)

    # a Fase 3 parte de uma Fase 2 aprovada, não de uma Visão
    async with session_scope() as s:
        await _expect_error(services.start_run(s, project_id, phase="3", agent_gateway="fake",
                                               base_run_id=phase1_id), 422)
    async with session_scope() as s:
        run_id = (await services.start_run(s, project_id, phase="3", agent_gateway="fake",
                                           base_run_id=phase2_id)).id
    await drain()

    req = await _open_request(run_id)
    assert req.kind == "consensus" and req.task_id == "3.2.7"
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        base = await store.current_version(s, phase2_id, "requirements.consolidated")
        explain = [r["id"] for r in base.content["requisitos"] if r["tipo"] == "EXPLICABILIDADE"]
        assert explain
        # um item por requisito de explicabilidade em cada análise por requisito
        for atype, field in [("analysis.characterized", "caracterizacoes"), ("analysis.aspects", "classificacoes"),
                             ("analysis.explanation_types", "mapeamentos"), ("analysis.dependencies", "dependencias"),
                             ("analysis.feasibility", "avaliacoes"), ("analysis.priorities", "prioridades")]:
            assert sorted(i["req_id"] for i in cur[atype].content[field]) == sorted(explain), atype
        # matriz de viabilidade completa: os quatro critérios, mesmo quando o agente omite algum
        for f in cur["analysis.feasibility"].content["avaliacoes"]:
            assert [c["criterio"] for c in f["criterios"]] == ["TECNICA", "REGULATORIA", "OPERACIONAL", "ECONOMICA"]
        conflicts = cur["analysis.conflicts"].content
        assert conflicts["cobertura_pares"]["avaliados"] == conflicts["cobertura_pares"]["candidatos"] > 0
        # a caracterização lê a Visão da Fase 1 (dois níveis acima) pela cadeia de execuções
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "3.1.2"))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        required = {i["artifact"] for i in pkg.items if i["origin"] == "required"}
        assert {"vision.stakeholders", "requirements.consolidated"} <= required
        digests = {i["artifact"] for i in pkg.items if i["origin"] == "digest"}
        assert {"digest.vision", "digest.requirements"} <= digests

    # objeção → retorno a 3.2 com o feedback; depois consenso e aprovação
    async with session_scope() as s:
        await services.record_position(s, req.id, participant, "objecao", "A prioridade do regulador está baixa",
                                       role="participant")
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "revisit_3_2", "Rever a priorização do regulador")
    await drain()
    req = await _open_request(run_id)
    assert req.task_id == "3.2.7" and req.iteracao == 2
    async with session_scope() as s:
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "3.2.6", TaskExecution.iteracao == 2))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        feedback = "\n".join(i["content"] for i in pkg.items if i["origin"] == "feedback")
        assert "Rever a priorização" in feedback and "prioridade do regulador" in feedback
        # 3.1 não foi refeita
        n = (await s.scalars(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                         TaskExecution.task_id == "3.1.2"))).all()
        assert len(n) == 1
        await services.record_position(s, req.id, participant, "concordo", role="participant")
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "close", None)
    await drain()

    req = await _open_request(run_id)
    assert req.kind == "approval" and req.task_id == "3.3.gate"
    async with session_scope() as s:
        report = await store.current_version(s, run_id, "analysis.review_report")
        checks = {c["id"]: c["ok"] for c in report.content["checks"]}
        assert checks["cobertura_priorities"] and checks["pares_avaliados"] and checks["consenso_sem_objecao"]
        await services.decide(s, req.id, engineer, "approve", None)
    await drain()

    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"
        cur = await store.current_versions(s, run_id)
        assert cur["analysis.draft"].status == "approved"
        assert cur["digest.analysis"].content["ids_faltantes"] == []
        links = (await s.scalars(select(TraceLink).where(TraceLink.run_id == run_id))).all()
        assert {lk.link_type for lk in links} >= {"refines", "conflicts_with"}
        exp = await s.scalar(select(Export).where(Export.run_id == run_id))
        text = Path(exp.storage_path).read_text(encoding="utf-8")
        for part in ("# Documento de Visão", "Requisitos de Explicabilidade — Elicitação",
                     "Análise dos Requisitos de Explicabilidade", "Priorização MoSCoW"):
            assert part in text, part


async def test_human_edit_keeps_system_fields(scope_bytes, law_bytes):
    project_id, _, phase2_id, engineer, _ = await _approved_phase2(scope_bytes, law_bytes)
    async with session_scope() as s:
        run_id = (await services.start_run(s, project_id, phase="3", agent_gateway="fake",
                                           base_run_id=phase2_id)).id
    await drain()
    async with session_scope() as s:
        v = await store.current_version(s, run_id, "analysis.priorities")
        content = {"prioridades": [dict(p, prioridade="COULD") for p in v.content["prioridades"]]}
        edited = await services.human_edit(s, v.id, content, engineer)
        assert edited.content["sugestao_ia"] is True
        assert {p["prioridade"] for p in edited.content["prioridades"]} == {"COULD"}
