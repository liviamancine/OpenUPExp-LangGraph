
import asyncio
import json
from copy import deepcopy
from datetime import datetime
from typing import TypedDict, Any

from pypdf import PdfReader
from langgraph.graph import StateGraph, START, END
#from langgraph.checkpoint.memory import MemorySaver
#from langgraph.types import interrupt, Command
from baml_client import b


# ============================================================
# LEITURA DO DOCUMENTO DE ESCOPO
# ============================================================

def ler_pdf(caminho: str) -> str:
    reader = PdfReader(caminho)

    texto = ""

    for pagina in reader.pages:
        texto += pagina.extract_text() or ""

    if not texto.strip():
        raise ValueError(
            f"Nenhum texto foi extraído do PDF: {caminho}"
        )

    return texto


# ============================================================
# CONFIGURAÇÃO DE EXECUÇÃO
# ============================================================

escopo_projeto = ler_pdf("documentos/escopo_projeto.pdf")


class OpenUPExpState(TypedDict):
    escopo_projeto: str
    blackboard: dict[str, Any]
    aprovado_fase_1: bool
    feedback_engenheiro: str


blackboard_inicial = {
    "visao_explicabilidade": {
        "escopo": None,
        "posicionamento": None,
        "stakeholders": None,
        "necessidades_funcionalidades": None,
    }
}


# ============================================================
# WORKER 1 — DEFINE EXPLAINABILITY NEED
# ============================================================

async def worker_1(state: OpenUPExpState):
    print("\nExecutando Worker 1 (Visão/Escopo da Explicabilidade)...")

    resultado = await b.AnalyzeExplainabilityScope(
        documento_escopo=state["escopo_projeto"]
    )

    blackboard = deepcopy(state["blackboard"])

    blackboard["visao_explicabilidade"]["escopo"] = (
        resultado.model_dump()
    )

    print("\n=== RESULTADO DO WORKER 1 ===")
    print(
        json.dumps(
            blackboard["visao_explicabilidade"]["escopo"],
            ensure_ascii=False,
            indent=2
        )
    )

    return {"blackboard": blackboard}


# ============================================================
# WORKER 2 — GENERATE EXPLAINABILITY POSITIONING
# ============================================================

async def worker_2(state: OpenUPExpState):
    print("\nExecutando Worker 2 (Posicionamento da Explicabilidade)...")

    # Recupera o objeto ExplainabilityScope do Worker 1.
    resultado_worker1 = (
        state["blackboard"]
        ["visao_explicabilidade"]
        ["escopo"]
        ["escopo"]
    )

    resultado = await b.GenerateExplainabilityPositioning(
        escopo_worker1=resultado_worker1,
        documento_bruto=state["escopo_projeto"]
    )

    blackboard = deepcopy(state["blackboard"])

    blackboard["visao_explicabilidade"]["posicionamento"] = (
        resultado.model_dump()
    )

    print("\n=== RESULTADO DO WORKER 2 ===")
    print(
        json.dumps(
            blackboard["visao_explicabilidade"]["posicionamento"],
            ensure_ascii=False,
            indent=2
        )
    )

    return {"blackboard": blackboard}


# ============================================================
# WORKER 3 — DESCRIBE STAKEHOLDERS
# ============================================================

async def worker_3(state: OpenUPExpState):
    print("\nExecutando Worker 3 (Resumo dos Stakeholders)...")

    resultado_worker2 = (
        state["blackboard"]
        ["visao_explicabilidade"]
        ["posicionamento"]
        ["posicionamentos"]
    )

    resultado = await b.DescribeStakeholders(
        resultado_worker2=resultado_worker2
    )

    blackboard = deepcopy(state["blackboard"])

    blackboard["visao_explicabilidade"]["stakeholders"] = (
        resultado.model_dump()
    )

    print("\n=== RESULTADO DO WORKER 3 ===")
    print(
        json.dumps(
            blackboard["visao_explicabilidade"]["stakeholders"],
            ensure_ascii=False,
            indent=2
        )
    )

    return {"blackboard": blackboard}


# ============================================================
# WORKER 4 — MAP EXPLAINABILITY NEEDS
# ============================================================

async def worker_4(state: OpenUPExpState):
    print(
        "\nExecutando Worker 4 "
        "(Mapeamento das Necessidades de Explicabilidade)..."
    )

    resultado_worker3 = (
        state["blackboard"]
        ["visao_explicabilidade"]
        ["stakeholders"]
        ["stakeholders"]
    )

    resultado = await b.MapExplainabilityNeeds(
        resultado_worker3=resultado_worker3
    )

    blackboard = deepcopy(state["blackboard"])

    blackboard["visao_explicabilidade"][
        "necessidades_funcionalidades"
    ] = resultado.model_dump()

    print("\n=== RESULTADO DO WORKER 4 ===")
    print(
        json.dumps(
            blackboard["visao_explicabilidade"][
                "necessidades_funcionalidades"
            ],
            ensure_ascii=False,
            indent=2
        )
    )

    return {"blackboard": blackboard}


# ============================================================
# COMPILADOR DO DOCUMENTO DE VISÃO EM MARKDOWN
# ============================================================


def compilar_markdown_parcial(blackboard: dict) -> str:
    visao = blackboard.get("visao_explicabilidade") or {}

    # --------------------------------------------------------
    # Tratamento de valores ausentes e caracteres especiais
    # --------------------------------------------------------

    def texto_md(valor, ausente="Pendente de investigação"):
        if valor is None or valor == "" or valor == []:
            return ausente

        if isinstance(valor, list):
            valor = ", ".join(str(item) for item in valor)

        return (
            str(valor)
            .replace("|", r"\|")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    # --------------------------------------------------------
    # Recuperação dos quatro artefatos do Blackboard
    # --------------------------------------------------------

    escopo_artifact = visao.get("escopo") or {}
    escopo = escopo_artifact.get("escopo") or {}

    posicionamento_artifact = visao.get("posicionamento") or {}
    posicionamentos = posicionamento_artifact.get(
        "posicionamentos", []
    )

    stakeholders_artifact = visao.get("stakeholders") or {}
    stakeholders = stakeholders_artifact.get("stakeholders", [])

    necessidades_artifact = (
        visao.get("necessidades_funcionalidades") or {}
    )
    necessidades = necessidades_artifact.get("necessidades", [])

    data_atual = datetime.now().strftime("%d/%m/%Y")

    # --------------------------------------------------------
    # 1. Definição da Explicabilidade
    # --------------------------------------------------------

    doc = f"""# Documento de Visão — Requisito de Explicabilidade

> **Domínio do problema:** {
        texto_md(escopo.get("dominio_do_problema"))
    }
>
> **Data de geração:** {data_atual}
>
> **Escopo:** Parcial — Workers 1 a 4

---

## 1. Definição da Explicabilidade

### 1.1 Necessidade de explicabilidade

{texto_md(escopo.get("necessidade_de_explicabilidade"))}

### 1.2 Descrição geral do sistema

{texto_md(escopo.get("descricao_geral"))}

### 1.3 Stakeholders afetados

{texto_md(escopo.get("stakeholders_afetados"), "Não identificados")}

### 1.4 Impactos identificados

{texto_md(escopo.get("impactos"), "Não identificados; requer investigação posterior")}

### 1.5 Critérios de sucesso

{texto_md(escopo.get("criterios_de_sucesso"))}

---

## 2. Posicionamento da Explicabilidade

"""

    if posicionamentos:
        for i, pos in enumerate(posicionamentos, start=1):
            doc += f"""### 2.{i} Stakeholder: {
                texto_md(pos.get("stakeholder"), "Não identificado")
            }

- **Para quem:** {texto_md(pos.get("para_quem"))}
- **Para quê:** {texto_md(pos.get("para_que"))}
- **Nome do produto:** {texto_md(pos.get("nome_produto"))}
- **Categoria do produto:** {texto_md(pos.get("categoria_produto"))}
- **Benefício-chave:** {texto_md(pos.get("beneficio_chave"))}
- **Unlike (alternativa de referência):** {texto_md(pos.get("unlike"))}
- **Our product (produto proposto):** {texto_md(pos.get("our_product"))}

"""
    else:
        doc += "Posicionamentos ainda não disponíveis.\n\n"

    # --------------------------------------------------------
    # 3. Descrição dos Stakeholders
    # --------------------------------------------------------

    doc += """---

## 3. Descrição dos Stakeholders

"""

    if stakeholders:
        for i, st in enumerate(stakeholders, start=1):
            doc += f"""### 3.{i} {texto_md(st.get("stakeholder"), "Stakeholder não identificado")}

- **Descrição:** {texto_md(st.get("descricao"))}
- **Responsabilidade:** {texto_md(st.get("responsabilidade"))}

"""
    else:
        doc += "Descrições dos stakeholders ainda não disponíveis.\n\n"

    # --------------------------------------------------------
    # 4. Necessidades de Explicabilidade
    # --------------------------------------------------------

    doc += """---

## 4. Visão Geral das Necessidades de Explicabilidade

"""

    if necessidades:
        for i, necessidade in enumerate(necessidades, start=1):
            doc += f"""### 4.{i} Necessidade de Explicabilidade

**Necessidade:** {texto_md(necessidade.get("necessidade"))}

- **Prioridade:** {texto_md(necessidade.get("prioridade"))}           
            
- **Planned release (versão planejada):** {
                texto_md(necessidade.get("planned_release"))
            }

"""
    else:
        doc += "Necessidades de explicabilidade ainda não disponíveis.\n\n"

    # --------------------------------------------------------
    # Observação sobre o estado do documento
    # --------------------------------------------------------

    doc += """---

## Observações sobre o documento

Este documento é parcial e foi compilado a partir dos artefatos
produzidos pelos Workers 1 a 4 da etapa Visão do OpenUPExp.

As informações ausentes ou indicadas como pendentes requerem
investigação posterior. Os posicionamentos e as necessidades
gerados devem ser analisados pelo Engenheiro de Requisitos antes
de serem considerados validados.

"""

    return doc


# # ============================================================
# # HUMAN-IN-THE-LOOP — VALIDAÇÃO PELO ENGENHEIRO DE REQUISITOS
# # ============================================================

# def hitl_validacao(state: OpenUPExpState):
#     print("\n" + "=" * 70)
#     print("VALIDAÇÃO HUMANA — WORKERS 1 A 4")
#     print("=" * 70)

#     doc_markdown = compilar_markdown_parcial(
#         state["blackboard"]
#     )

#     decisao = interrupt({
#         "mensagem": (
#             "Validação parcial da Etapa de Visão "
#             "(Workers 1 a 4)."
#         ),
#         "documento_preview": doc_markdown
#     })

#     aprovado = decisao.get("aprovado", False)
#     feedback = decisao.get("comentario", "")

#     if aprovado:
#         with open(
#             "Documento_de_Visao_Explicabilidade_Parcial.md",
#             "w",
#             encoding="utf-8"
#         ) as arquivo:
#             arquivo.write(doc_markdown)

#         print(
#             "\nDocumento exportado: "
#             "Documento_de_Visao_Explicabilidade_Parcial.md"
#         )
#     else:
#         print(
#             "\nDocumento não aprovado. "
#             "Feedback registrado para análise posterior."
#         )

#     return {
#         "aprovado_fase_1": aprovado,
#         "feedback_engenheiro": feedback
#     }


# ============================================================
# CONSTRUÇÃO DO GRAFO
# ============================================================


# ============================================================
# CONSTRUÇÃO DO GRAFO
# ============================================================

builder = StateGraph(OpenUPExpState)

builder.add_node("worker_1", worker_1)
builder.add_node("worker_2", worker_2)
builder.add_node("worker_3", worker_3)
builder.add_node("worker_4", worker_4)

builder.add_edge(START, "worker_1")
builder.add_edge("worker_1", "worker_2")
builder.add_edge("worker_2", "worker_3")
builder.add_edge("worker_3", "worker_4")
builder.add_edge("worker_4", END)

graph = builder.compile()

# ============================================================
# EXECUÇÃO
# ============================================================


async def main():
    state_inicial = {
        "escopo_projeto": escopo_projeto,
        "blackboard": deepcopy(blackboard_inicial),
        "aprovado_fase_1": False,
        "feedback_engenheiro": ""
    }

    print(
        "\nIniciando execução encadeada "
        "dos Workers 1, 2, 3 e 4..."
    )

    estado_final = await graph.ainvoke(state_inicial)

    # Persiste o Blackboard
    with open(
        "blackboard.json",
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(
            estado_final["blackboard"],
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    # Gera o documento parcial de Visão
    documento = compilar_markdown_parcial(
        estado_final["blackboard"]
    )

    with open(
        "Documento_de_Visao_Explicabilidade_Parcial.md",
        "w",
        encoding="utf-8"
    ) as arquivo:
        arquivo.write(documento)

    print("\nDocumento parcial gerado: Documento_de_Visao_Explicabilidade_Parcial.md")
    print("Blackboard salvo: blackboard.json")

    print("\n" + "=" * 70)
    print("BLACKBOARD FINAL")
    print("=" * 70)

    print(
        json.dumps(
            estado_final["blackboard"],
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
