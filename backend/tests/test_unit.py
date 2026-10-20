"""Testes sem banco: manifesto, chunking, citações, IDs, diff e independência de domínio."""

import re
from pathlib import Path

from openupexp.agents.phase1 import HANDLERS
from openupexp.config import get_settings
from openupexp.domain.diff import diff_contents
from openupexp.domain.ids import assign_keys
from openupexp.process.manifest import check_conformance, load_manifest
from openupexp.retrieval.chunkers import Page, chunk_law, chunk_manual
from openupexp.retrieval.citations import verify_quote
from openupexp.retrieval.search import explicit_refs

from .conftest import LAW_TEXT

BAML_SRC = Path(__file__).resolve().parents[1] / "baml_src"


def test_manifest_conforms_to_bpmn():
    assert check_conformance(load_manifest(), get_settings().bpmn_dir) == []


def test_phase1_tasks_have_handlers_and_inputs_are_produced_before_use():
    phase = load_manifest().phase("1")
    produced = {"project.scope_document"}
    for t in phase.tasks():
        if t.mechanism in ("agent", "deterministic") and t.handler != "consolidate_vision":
            assert t.id in HANDLERS, f"tarefa {t.id} sem handler"
        for r in t.reads:
            if r.required:
                assert r.artifact in produced, f"{t.id} lê {r.artifact} antes de ser produzido"
        produced |= {w.artifact for w in t.writes}


def test_gate_outcomes_follow_bpmn_annotation():
    gate = load_manifest().task("1.3.gate")
    assert set(gate.outcomes) == {"approve", "revisit_1_1", "revisit_1_2"}
    assert gate.outcomes["revisit_1_1"].comment_required


def test_law_chunker_splits_by_article():
    chunks = chunk_law("lgpd", [Page(1, LAW_TEXT)])
    keys = [c.stable_key for c in chunks]
    assert "lgpd:art20" in keys and "lgpd:art1" in keys
    art20 = next(c for c in chunks if c.stable_key == "lgpd:art20")
    assert art20.meta == {"lei_numero": "13.709", "artigo": "20"}
    assert "§ 1º" in art20.texto  # parágrafo permanece com o caput


def test_manual_chunker_merges_table_of_contents():
    toc = "\n".join(f"5.{i} Seção número {i}" for i in range(1, 8))
    body = "5.8 Análise da distintividade\n" + ("Texto do manual sobre distintividade. " * 40)
    chunks = chunk_manual("manual", [Page(1, toc + "\n" + body)])
    assert all(len(c.texto) >= 200 for c in chunks)


def test_citation_verification():
    src = "O titular dos dados tem direito a solicitar a revisão de decisões tomadas unica-\nmente com base"
    assert verify_quote("tem direito a solicitar a revisão de decisões tomadas unicamente", src)
    assert verify_quote("“O titular dos dados” ... “revisão de decisões”", src)
    assert not verify_quote("tem direito a obter explicação completa do algoritmo", src)
    assert not verify_quote("curta", src)


def test_explicit_references():
    arts, laws = explicit_refs("Como o Art. 20 da Lei 13.709/2018 se aplica?")
    assert arts == ["20"] and laws == ["13.709"]


def test_assign_keys_preserves_and_matches():
    existing = {"STK-01": {"id": "STK-01", "nome": "Examinador"}, "STK-02": {"id": "STK-02", "nome": "Solicitante"}}
    out = assign_keys("STK", [{"id": "STK-02", "nome": "Solicitante"}, {"id": None, "nome": "Examinador"},
                              {"id": "STK-99", "nome": "Regulador"}], existing, lambda i: i["nome"])
    assert [k for k, _ in out] == ["STK-02", "STK-01", "STK-03"]


def test_diff_by_item():
    old = {"stakeholders": [{"id": "STK-01", "nome": "A"}, {"id": "STK-02", "nome": "B"}]}
    new = {"stakeholders": [{"id": "STK-01", "nome": "A2"}, {"id": "STK-03", "nome": "C"}]}
    d = diff_contents("vision.stakeholders", old, new)
    assert [i["id"] for i in d["adicionados"]] == ["STK-03"]
    assert [i["id"] for i in d["removidos"]] == ["STK-02"]
    assert d["alterados"][0]["campos"][0] == {"campo": "nome", "antes": "A", "depois": "A2"}


DOMAIN_TERMS = ["inpi", "marca", "marcário", "propriedade industrial", "lpi", "financiamento", "imobiliário",
                "crédito"]


def test_prompts_are_domain_independent():
    for f in BAML_SRC.glob("*.baml"):
        text = f.read_text(encoding="utf-8").lower()
        for term in DOMAIN_TERMS:
            assert not re.search(rf"\b{re.escape(term)}\b", text), f"termo de domínio '{term}' em {f.name}"


async def test_prompt_renders_feedback_without_llm():
    from openupexp.baml_client import types as T
    from openupexp.baml_client.async_client import b

    req = await b.request.DefineExplainabilityProblem(
        T.DefineProblemInput(documento_escopo="ESCOPO X"),
        [T.ContextItem(origem="feedback", referencia="hitl_response:1", conteudo="faltou o regulador")],
    )
    content = str(req.body.json())
    assert "ESCOPO X" in content and "faltou o regulador" in content and "FEEDBACK DO REVISOR" in content
    assert "NÃO INVENÇÃO" in content
