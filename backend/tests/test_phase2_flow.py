"""Fluxo completo da Fase 2 com gateway simulado: material de elicitação, consenso, revisit, aprovação."""

from pathlib import Path

from sqlalchemy import select

from openupexp.api.auth import create_user
from openupexp.db.models import (
    ContextPackageRow,
    Evidence,
    Export,
    HitlRequest,
    ProjectMember,
    Run,
    TaskExecution,
    TraceLink,
)
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.retrieval.embeddings import HashEmbedder
from openupexp.retrieval.ingest import add_source, build_corpus_version
from openupexp.worker_main import drain

# Material SINTÉTICO, escrito só para o teste: não é transcrição real de elicitação.
ELICITATION_TEXT = """Transcrição fictícia de entrevista (material sintético para testes da plataforma).
Entrevistador: Como as decisões do sistema afetam o seu trabalho?
Resposta: Quando o pedido é indeferido, o solicitante quer saber qual critério não foi atendido.
Resposta: O examinador precisa ver quais precedentes o sistema considerou na recomendação.
Resposta: O regulador quer rastrear quem confirmou cada recomendação automatizada.
"""


async def _expect_error(coro, status: int) -> None:
    try:
        await coro
    except services.DomainError as e:
        assert e.status == status, e
        return
    raise AssertionError(f"deveria falhar com {status}")


async def _open_request(run_id):
    async with session_scope() as s:
        return await s.scalar(select(HitlRequest).where(HitlRequest.run_id == run_id, HitlRequest.status == "open"))


async def _approved_phase1(scope_bytes, law_bytes):
    async with session_scope() as s:
        p = await services.create_project(s, "Fase 2", None, None, None)
        await add_source(s, p.id, "escopo.txt", scope_bytes, "escopo")
        await add_source(s, p.id, "lei_13709_lgpd.txt", law_bytes, "lei")
        await build_corpus_version(s, p.id, HashEmbedder())
        engineer = await create_user(s, "eng@teste.org", "Engenheira", "senha-segura")
        participant = await create_user(s, "part@teste.org", "Participante", "senha-segura")
        s.add(ProjectMember(project_id=p.id, user_id=engineer.id, papel_plataforma="requirements_engineer"))
        s.add(ProjectMember(project_id=p.id, user_id=participant.id, papel_plataforma="participant"))
        run = await services.start_run(s, p.id, agent_gateway="fake")
        ids = p.id, run.id, engineer.id, participant.id
    await drain()
    req = await _open_request(ids[1])
    async with session_scope() as s:
        await services.decide(s, req.id, None, "approve", None, bypass_role_check=True)
    await drain()
    return ids


async def test_phase2_full_flow(scope_bytes, law_bytes):
    project_id, base_id, engineer, participant = await _approved_phase1(scope_bytes, law_bytes)

    # a Fase 2 exige uma Visão aprovada como base
    async with session_scope() as s:
        await _expect_error(services.start_run(s, project_id, phase="2", agent_gateway="fake"), 422)
    async with session_scope() as s:
        run2 = await services.start_run(s, project_id, phase="2", agent_gateway="fake", base_run_id=base_id)
        run_id = run2.id
    await drain()

    # 2.2.1 aguarda o material de elicitação
    req = await _open_request(run_id)
    assert req.kind == "input" and req.task_id == "2.2.1.in"
    async with session_scope() as s:
        await _expect_error(services.decide(s, req.id, None, "submit", None, bypass_role_check=True), 422)
        cur = await store.current_versions(s, run_id)
        assert len(cur["elicitation.plan"].content["itens"]) == 3  # um item por stakeholder
    async with session_scope() as s:
        await add_source(s, project_id, "entrevistas.txt", ELICITATION_TEXT.encode(), "elicitacao")
    async with session_scope() as s:
        await services.decide(s, req.id, None, "submit", None, bypass_role_check=True)
    await drain()

    # 2.2.5 consenso: objeção exige comentário e bloqueia o encerramento sem justificativa
    req = await _open_request(run_id)
    assert req.kind == "consensus" and req.task_id == "2.2.5" and req.iteracao == 1
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        rns = cur["elicitation.needs"].content["necessidades"]
        assert rns and all(n["fundamentacao_verificada"] for n in rns)
        evidences = (await s.scalars(select(Evidence).where(
            Evidence.artifact_version_id == cur["elicitation.needs"].id))).all()
        assert evidences and {e.verification for e in evidences} == {"verified"}
        assert all(e.chunk_id is not None for e in evidences)  # citações do material, não da Visão
        await _expect_error(services.record_position(s, req.id, participant, "objecao", "", role="participant"), 422)
        await _expect_error(services.record_position(s, req.id, participant, "concordo", role="observer"), 403)
    async with session_scope() as s:
        await services.record_position(s, req.id, participant, "objecao",
                                       "Falta o requisito sobre prazos de recurso", role="participant")
    async with session_scope() as s:
        await _expect_error(services.decide(s, req.id, engineer, "close", None), 422)
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "revisit_2_2", "Incluir prazos de recurso")
    await drain()

    # o retorno a 2.2 pede o material de novo (iteração 2) e leva o feedback aos agentes
    req = await _open_request(run_id)
    assert req.kind == "input" and req.iteracao == 2
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "submit", None)
    await drain()
    req = await _open_request(run_id)
    assert req.kind == "consensus" and req.iteracao == 2
    async with session_scope() as s:
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id,
                                                        TaskExecution.task_id == "2.2.2", TaskExecution.iteracao == 2))
        pkg = await s.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te.id))
        feedback = "\n".join(i["content"] for i in pkg.items if i["origin"] == "feedback")
        assert "Incluir prazos de recurso" in feedback and "Falta o requisito sobre prazos" in feedback
        await services.record_position(s, req.id, participant, "concordo", role="participant")
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "close", None)
    await drain()

    # 2.3 aprovação com checklist
    req = await _open_request(run_id)
    assert req.kind == "approval" and req.task_id == "2.3.gate"
    async with session_scope() as s:
        report = await store.current_version(s, run_id, "requirements.review_report")
        checks = {c["id"]: c["ok"] for c in report.content["checks"]}
        assert checks["material_elicitacao"] and checks["origem_consolidada"] and checks["consenso_sem_objecao"]
        await services.decide(s, req.id, engineer, "approve", None)
    await drain()

    async with session_scope() as s:
        assert (await s.get(Run, run_id)).status == "completed"
        cur = await store.current_versions(s, run_id)
        assert cur["requirements.draft"].status == "approved"
        assert cur["requirements.consolidated"].status == "approved"
        assert cur["digest.requirements"].content["ids_faltantes"] == []
        reqs = cur["requirements.consolidated"].content["requisitos"]
        assert reqs and all(r["id"].startswith("REQ-") for r in reqs)
        links = (await s.scalars(select(TraceLink).where(TraceLink.run_id == run_id,
                                                         TraceLink.from_item_key.like("REQ-%")))).all()
        assert {lk.to_item_key[:3] for lk in links} >= {"RI-"}
        exp = await s.scalar(select(Export).where(Export.run_id == run_id))
        text = Path(exp.storage_path).read_text(encoding="utf-8")
        assert "Documento de Requisitos de Explicabilidade" in text and "# Documento de Visão" in text
        assert "Registro de consenso" in text and "objeção" not in text.split("Registro de consenso")[1][:20]


async def test_phase2_without_material_requires_justification(scope_bytes, law_bytes):
    project_id, base_id, engineer, _ = await _approved_phase1(scope_bytes, law_bytes)
    async with session_scope() as s:
        run_id = (await services.start_run(s, project_id, phase="2", agent_gateway="fake",
                                           base_run_id=base_id)).id
    await drain()
    req = await _open_request(run_id)
    async with session_scope() as s:
        await _expect_error(services.decide(s, req.id, engineer, "no_material", ""), 422)
    async with session_scope() as s:
        await services.decide(s, req.id, engineer, "no_material", "Entrevistas ainda não agendadas")
    await drain()
    async with session_scope() as s:
        cur = await store.current_versions(s, run_id)
        assert cur["elicitation.sources"].content["justificativa"] == "Entrevistas ainda não agendadas"
        rns = cur["elicitation.needs"].content["necessidades"]
        # sem material, as necessidades vêm das solicitações (SN) da Visão, também com citação verificada
        assert rns and all(e["fonte_ref"].startswith("SN-") for n in rns for e in n["evidencias"])
        assert all(n["fundamentacao_verificada"] for n in rns)
