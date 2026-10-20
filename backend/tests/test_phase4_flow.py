"""Fluxo completo da Fase 4 (Especificação) sobre uma Fase 3 aprovada, com gateway simulado."""

from pathlib import Path

from sqlalchemy import select

from openupexp.db.models import ContextPackageRow, Export, Run, TaskExecution, TraceLink
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.worker_main import drain

from .test_phase2_flow import _expect_error, _open_request
from .test_phase3_flow import _approved_phase2


async def _approved_phase3(scope_bytes, law_bytes):
    project_id, _, phase2_id, engineer, participant = await _approved_phase2(scope_bytes, law_bytes)
    async with session_scope() as s:
        run_id = (await services.start_run(s, project_id, phase="3", agent_gateway="fake",
                                           base_run_id=phase2_id)).id
    await drain()
    for decision in ("close", "approve"):
        req = await _open_request(run_id)
        async with session_scope() as s:
            if decision == "close":
                await services.record_position(s, req.id, participant, "concordo", role="participant")
            await services.decide(s, req.id, engineer, decision, None)
        await drain()
    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"
    return project_id, phase2_id, run_id, engineer, participant


async def test_phase4_full_flow(scope_bytes, law_bytes):
    project_id, phase2_id, phase3_id, engineer, participant = await _approved_phase3(scope_bytes, law_bytes)

    # a Fase 4 parte de uma Fase 3 aprovada
    async with session_scope() as s:
        await _expect_error(services.start_run(s, project_id, phase="4", agent_gateway="fake",
                                               base_run_id=phase2_id), 422)
    async with session_scope() as s:
        run_id = (await services.start_run(s, project_id, phase="4", agent_gateway="fake",
                                           base_run_id=phase3_id)).id
    await drain()

    req = await _open_request(run_id)
    assert req.kind == "consensus" and req.task_id == "4.2.5"
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        prios = (await store.current_version(s, phase3_id, "analysis.priorities")).content["prioridades"]
        planned = {p["req_id"] for p in prios if p["prioridade"] != "WONT"}
        fichas = cur["specification.plan"].content["fichas"]
        assert {f["req_id"] for f in fichas} == planned
        stories = cur["specification.user_stories"].content["historias"]
        assert {h["req_id"] for h in stories} == planned
        hu_ids = sorted(h["id"] for h in stories)
        assert len(hu_ids) >= len(planned) and all(i.startswith("HU-") for i in hu_ids)
        for atype, field in [("specification.acceptance_criteria", "criterios"),
                             ("specification.characteristics", "caracteristicas")]:
            assert sorted(i["hu_id"] for i in cur[atype].content[field]) == hu_ids, atype
        rows = cur["specification.traceability"].content["linhas"]
        assert sorted(r["hu"] for r in rows) == hu_ids
        assert all(r["ca"] and r["cex"] and r["rer"] and r["prioridade"] for r in rows)
        assert cur["specification.traceability"].content["requisitos_sem_hu"] == []
        # as fichas vêm da Análise (dois níveis de base acima para os stakeholders da Visão)
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "4.2.1"))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        required = {i["artifact"] for i in pkg.items if i["origin"] == "required"}
        assert {"specification.plan", "vision.stakeholders"} <= required
        digests = {i["artifact"] for i in pkg.items if i["origin"] == "digest"}
        assert {"digest.vision", "digest.requirements", "digest.analysis"} <= digests

    # objeção → retorno a 4.2 com feedback, IDs das HU preservados
    async with session_scope() as s:
        await services.record_position(s, req.id, participant, "objecao", "Falta tempo de resposta no critério",
                                       role="participant")
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "revisit_4_2", "Tornar os critérios mensuráveis")
    await drain()
    req = await _open_request(run_id)
    assert req.task_id == "4.2.5" and req.iteracao == 2
    async with session_scope() as s:
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "4.2.2", TaskExecution.iteracao == 2))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        feedback = "\n".join(i["content"] for i in pkg.items if i["origin"] == "feedback")
        assert "critérios mensuráveis" in feedback and "tempo de resposta" in feedback
        stories = (await store.current_version(s, run_id, "specification.user_stories")).content["historias"]
        assert sorted(h["id"] for h in stories) == hu_ids
        await services.record_position(s, req.id, participant, "concordo", role="participant")
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "close", None)
    await drain()

    req = await _open_request(run_id)
    assert req.kind == "approval" and req.task_id == "4.3.gate"
    async with session_scope() as s:
        report = await store.current_version(s, run_id, "specification.review_report")
        checks = {c["id"]: c["ok"] for c in report.content["checks"]}
        for check in ("requisito_com_hu", "hu_formato", "hu_com_criterios", "hu_com_caracteristicas",
                      "rastreabilidade_completa", "consenso_sem_objecao", "sem_stale"):
            assert checks[check], check
        await services.decide(s, req.id, engineer, "approve", None)
    await drain()

    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"
        cur = await store.current_versions(s, run_id)
        assert cur["specification.draft"].status == "approved"
        assert cur["digest.specification"].content["ids_faltantes"] == []
        links = (await s.scalars(select(TraceLink).where(TraceLink.run_id == run_id))).all()
        assert {lk.link_type for lk in links} >= {"refines", "specifies", "relates_to"}
        exp = await s.scalar(select(Export).where(Export.run_id == run_id))
        text = Path(exp.storage_path).read_text(encoding="utf-8")
        for part in ("# Documento de Visão", "Requisitos de Explicabilidade — Elicitação",
                     "Análise dos Requisitos de Explicabilidade", "Especificação dos Requisitos de Explicabilidade",
                     "**Como**", "**Dado**", "Matriz de rastreabilidade"):
            assert part in text, part


async def test_vague_criteria_are_flagged():
    from openupexp.agents.phase4 import _vague

    assert _vague({"entao": "a explicação é apresentada de forma adequada"})
    assert not _vague({"entao": "a explicação é apresentada em até 3 segundos de forma adequada"})
    assert not _vague({"entao": "o sistema lista as anterioridades consideradas"})
