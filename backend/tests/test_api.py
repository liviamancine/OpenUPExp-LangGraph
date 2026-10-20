"""API: autenticação, RBAC, upload, execução, decisão, edição e documento."""

import httpx
import pytest

from openupexp.api.auth import create_user
from openupexp.api.main import app
from openupexp.db.session import session_scope
from openupexp.worker_main import drain


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _login(client, email, password="senha123"):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_end_to_end_via_api(client, scope_bytes, law_bytes):
    async with session_scope() as s:
        await create_user(s, "eng@x.org", "Engenheira", "senha123")
        part = await create_user(s, "stk@x.org", "Stakeholder", "senha123")
        part_id = str(part.id)
    eng = await _login(client, "eng@x.org")
    stk = await _login(client, "stk@x.org")

    assert (await client.get("/api/projects")).status_code == 401
    p = (await client.post("/api/projects", json={"nome": "API"}, headers=eng)).json()
    pid = p["id"]
    r = await client.post(f"/api/projects/{pid}/members", headers=eng,
                          json={"user_id": part_id, "papel_plataforma": "participant",
                                "papel_openupexp": "Especialista em Regulação"})
    assert r.status_code == 200
    r = await client.post(f"/api/projects/{pid}/sources", headers=eng,
                          files={"file": ("escopo.txt", scope_bytes)}, data={"source_kind": "escopo"})
    assert r.status_code == 200 and r.json()["source_kind"] == "escopo"
    await client.post(f"/api/projects/{pid}/sources", headers=eng, files={"file": ("lei_13709.txt", law_bytes)},
                      data={"source_kind": "lei"})
    assert (await client.post(f"/api/projects/{pid}/corpus", headers=eng)).status_code == 200
    await drain()

    # participante não inicia execuções
    assert (await client.post(f"/api/projects/{pid}/runs", headers=stk, json={})).status_code == 403
    run = (await client.post(f"/api/projects/{pid}/runs", headers=eng,
                             json={"agent_gateway": "fake", "context_strategy": "D"})).json()
    await drain()
    detail = (await client.get(f"/api/runs/{run['id']}", headers=eng)).json()
    assert detail["status"] == "waiting_human" and detail["pending_hitl"]

    tasks = (await client.get(f"/api/runs/{run['id']}/tasks", headers=stk)).json()
    assert [t["task_id"] for t in tasks][:3] == ["1.1.1", "1.1.2", "1.1.3"]
    te = (await client.get(f"/api/task-executions/{tasks[1]['id']}", headers=eng)).json()
    assert te["context_package"]["strategy"].startswith("D") and te["llm_calls"]

    arts = (await client.get(f"/api/runs/{run['id']}/artifacts", headers=eng)).json()
    stk_art = next(a for a in arts if a["artifact_type"] == "vision.stakeholders")
    version = (await client.get(f"/api/artifact-versions/{stk_art['id']}", headers=eng)).json()
    assert version["editavel"] and version["content"]["stakeholders"]

    content = version["content"]
    content["stakeholders"][0]["descricao"] = "Descrição revisada"
    assert (await client.post(f"/api/artifact-versions/{stk_art['id']}/edits", headers=stk,
                              json={"content": content})).status_code == 403
    edited = (await client.post(f"/api/artifact-versions/{stk_art['id']}/edits", headers=eng,
                                json={"content": content})).json()
    d = (await client.get(f"/api/artifact-versions/{edited['id']}/diff/{stk_art['id']}", headers=eng)).json()
    assert d["alterados"][0]["campos"][0]["depois"] == "Descrição revisada"

    hitl_id = detail["pending_hitl"]
    req = (await client.get(f"/api/hitl/{hitl_id}", headers=eng)).json()
    assert req["review_report"]["checks"]
    assert (await client.post(f"/api/hitl/{hitl_id}/responses", headers=stk,
                              json={"decision": "approve"})).status_code == 403
    assert (await client.post(f"/api/hitl/{hitl_id}/responses", headers=eng,
                              json={"decision": "approve"})).status_code == 200
    assert (await client.post(f"/api/hitl/{hitl_id}/responses", headers=eng,
                              json={"decision": "approve"})).status_code == 409
    await drain()
    assert (await client.get(f"/api/runs/{run['id']}", headers=eng)).json()["status"] == "completed"
    exports = (await client.get(f"/api/runs/{run['id']}/exports", headers=eng)).json()
    md = await client.get(f"/api/exports/{exports[0]['id']}/download", headers=eng)
    assert "Descrição revisada" in md.text

    bpmn = await client.get("/api/process/bpmn/1.3 Validate Explainability Vision.bpmn", headers=eng)
    assert bpmn.status_code == 200 and b"Id_d7c8e559" in bpmn.content
    assert (await client.get("/api/process/bpmn/..%2F..%2Fsecret.bpmn", headers=eng)).status_code == 404
    metrics = (await client.get(f"/api/runs/{run['id']}/metrics", headers=eng)).json()
    assert metrics["total"]["llm_calls"] > 0


async def test_phase2_human_points_via_api(client, scope_bytes, law_bytes):
    async with session_scope() as s:
        await create_user(s, "eng2@x.org", "Engenheira", "senha123")
        part = await create_user(s, "part2@x.org", "Participante", "senha123")
        obs = await create_user(s, "obs2@x.org", "Observador", "senha123")
        part_id, obs_id = str(part.id), str(obs.id)
    eng = await _login(client, "eng2@x.org")
    stk = await _login(client, "part2@x.org")
    observer = await _login(client, "obs2@x.org")
    pid = (await client.post("/api/projects", json={"nome": "API F2"}, headers=eng)).json()["id"]
    for uid, role in ((part_id, "participant"), (obs_id, "observer")):
        await client.post(f"/api/projects/{pid}/members", headers=eng, json={"user_id": uid, "papel_plataforma": role})
    await client.post(f"/api/projects/{pid}/sources", headers=eng, files={"file": ("escopo.txt", scope_bytes)},
                      data={"source_kind": "escopo"})
    base = (await client.post(f"/api/projects/{pid}/runs", headers=eng, json={"agent_gateway": "fake"})).json()["id"]
    await drain()
    gate = (await client.get(f"/api/runs/{base}", headers=eng)).json()["pending_hitl"]
    await client.post(f"/api/hitl/{gate}/responses", headers=eng, json={"decision": "approve"})
    await drain()

    r = await client.post(f"/api/projects/{pid}/runs", headers=eng, json={"phase": "2", "agent_gateway": "fake"})
    assert r.status_code == 422  # exige a Visão de base
    run = (await client.post(f"/api/projects/{pid}/runs", headers=eng,
                             json={"phase": "2", "agent_gateway": "fake", "base_run_id": base})).json()["id"]
    await drain()
    req = (await client.get(f"/api/runs/{run}", headers=eng)).json()["pending_hitl"]
    detail = (await client.get(f"/api/hitl/{req}", headers=eng)).json()
    assert detail["kind"] == "input" and detail["material"] == []
    r = await client.post(f"/api/projects/{pid}/sources", headers=eng, data={"source_kind": "elicitacao"},
                          files={"file": ("entrevista.txt", "O examinador quer ver os critérios usados.".encode())})
    assert r.status_code == 200
    assert (await client.post(f"/api/hitl/{req}/responses", headers=eng, json={"decision": "submit"})).status_code == 200
    await drain()

    req = (await client.get(f"/api/runs/{run}", headers=eng)).json()["pending_hitl"]
    assert (await client.get(f"/api/hitl/{req}", headers=stk)).json()["kind"] == "consensus"
    r = await client.post(f"/api/hitl/{req}/positions", headers=observer, json={"posicao": "concordo"})
    assert r.status_code == 403
    r = await client.post(f"/api/hitl/{req}/positions", headers=stk, json={"posicao": "concordo"})
    assert r.status_code == 200
    # participante não encerra o consenso
    assert (await client.post(f"/api/hitl/{req}/responses", headers=stk, json={"decision": "close"})).status_code == 403
    assert (await client.get(f"/api/hitl/{req}", headers=eng)).json()["consenso"]["concordo"] == 1
    assert (await client.post(f"/api/hitl/{req}/responses", headers=eng, json={"decision": "close"})).status_code == 200
    await drain()
    detail = (await client.get(f"/api/hitl/{(await client.get(f'/api/runs/{run}', headers=eng)).json()['pending_hitl']}",
                               headers=eng)).json()
    assert detail["kind"] == "approval" and detail["review_report"]["checks"]
    arts = (await client.get(f"/api/runs/{run}/artifacts", headers=eng)).json()
    assert {a["artifact_type"] for a in arts if a["secao"]} >= {"elicitation.plan", "requirements.consolidated"}
