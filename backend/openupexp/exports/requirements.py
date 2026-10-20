"""Renderização da parte da Fase 2 do ERD (requisitos elicitados) em Markdown."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.context.builder import CONSENSUS_POSITIONS
from openupexp.db.models import AppUser, HitlRequest, HitlResponse, Run
from openupexp.domain import artifacts as store
from openupexp.exports.vision import _env

TEMPLATE_VERSION = "requisitos-0.1-provisorio"


def _lacunas(contents: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for atype, field, label in [
        ("elicitation.plan", "itens", "Plano"),
        ("elicitation.needs", "necessidades", "Necessidade elicitada"),
        ("requirements.identified", "requisitos", "Requisito identificado"),
        ("requirements.consolidated", "requisitos", "Requisito"),
    ]:
        for item in (contents.get(atype) or {}).get(field, []):
            out += [(f"{label} {item.get('id')}", lac) for lac in item.get("lacunas", [])]
    return out


def render_requirements_markdown(contents: dict[str, dict], base: dict[str, dict], meta: dict,
                                 consensus: list[dict] | None = None) -> str:
    stakeholders = (base.get("vision.stakeholders") or {}).get("stakeholders", [])
    names = {s.get("id"): s.get("nome") for s in stakeholders}
    consolidated = (contents.get("requirements.consolidated") or {}).get("requisitos", [])
    needs = (base.get("vision.explainability_needs") or {}).get("necessidades", [])
    need_matrix = [(n.get("id"), [r.get("id") for r in consolidated if n.get("id") in (r.get("need_ids") or [])])
                   for n in needs]
    return _env.get_template("requisitos.md.j2").render(
        meta=meta,
        plan=(contents.get("elicitation.plan") or {}).get("itens", []),
        sources=contents.get("elicitation.sources"),
        elicited=(contents.get("elicitation.needs") or {}).get("necessidades", []),
        consolidated=consolidated,
        discarded=(contents.get("requirements.consolidated") or {}).get("descartados", []),
        complementary=(contents.get("requirements.complementary") or {}).get("requisitos", []),
        need_matrix=need_matrix,
        consensus=consensus or [],
        lacunas=_lacunas(contents),
        stakeholder_name=lambda sid: f"{sid} {names[sid]}" if sid in names else sid,
    )


async def consensus_records(session: AsyncSession, run: Run) -> list[dict]:
    """Rodadas de consenso decididas, com as posições registradas pelos participantes."""
    requests = (await session.scalars(
        select(HitlRequest).where(HitlRequest.run_id == run.id, HitlRequest.kind == "consensus",
                                  HitlRequest.status == "decided").order_by(HitlRequest.created_at))).all()
    out = []
    for req in requests:
        rows = (await session.execute(
            select(HitlResponse, AppUser).outerjoin(AppUser, AppUser.id == HitlResponse.user_id)
            .where(HitlResponse.hitl_request_id == req.id).order_by(HitlResponse.created_at))).all()
        latest: dict = {}
        decision = None
        for resp, user in rows:
            if resp.decision in CONSENSUS_POSITIONS:
                latest[resp.user_id] = {"nome": user.nome if user else "—", "posicao": resp.decision,
                                        "comentario": resp.comentario}
            else:
                decision = resp
        fechamento = (req.payload or {}).get("fechamento", {})
        resultado = {"close": "consenso encerrado", "revisit_2_2": "retorno a 2.2"}.get(
            decision.decision if decision else "", decision.decision if decision else "—")
        if fechamento.get("override"):
            resultado += " com objeções registradas"
        out.append({"iteracao": req.iteracao, "resultado": resultado,
                    "justificativa": decision.comentario if decision else None,
                    "posicoes": list(latest.values())})
    return out


async def base_contents(session: AsyncSession, run: Run) -> dict[str, dict]:
    if not run.base_run_id:
        return {}
    return {t: v.content for t, v in (await store.current_versions(session, run.base_run_id)).items()}
