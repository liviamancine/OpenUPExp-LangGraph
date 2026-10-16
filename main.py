
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
from rag_retriever import RAGRetriever


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

escopo_projeto = ler_pdf("documentos RAG/escopo_projeto.pdf")


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
        "consulta_requisitos_adicionais": None,
        "conhecimento_recuperado": None,
        "requisitos_adicionais_explicabilidade": None,
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
# WORKER 5 — GERA CONSULTA PARA RECUPERAÇÃO RAG
# ============================================================

async def worker_5(state: OpenUPExpState):
    print("\\nExecutando Worker 5 (Consulta para Requisitos Adicionais)...")

    documento_visao = compilar_markdown_parcial(state["blackboard"])

    resultado = await b.GenerateAdditionalRequirementsQuery(
        documento_escopo=state["escopo_projeto"],
        documento_visao=documento_visao,
    )

    consulta = resultado.consulta.strip()
    if not consulta:
        raise ValueError("O Worker 5 retornou uma consulta vazia.")

    blackboard = deepcopy(state["blackboard"])
    blackboard["visao_explicabilidade"][
        "consulta_requisitos_adicionais"
    ] = {
        "consulta": consulta
    }

    print("\\n=== CONSULTA DO WORKER 5 ===")
    print(consulta)

    return {"blackboard": blackboard}


# ============================================================
# WORKER 6 — ELABORA REQUISITOS ADICIONAIS COM EVIDÊNCIAS DO RAG
# ============================================================

async def worker_6(state: OpenUPExpState):
    print("\\nExecutando Worker 6 (Requisitos Adicionais de Explicabilidade)...")

    visao = state["blackboard"]["visao_explicabilidade"]
    consulta_artifact = visao.get("consulta_requisitos_adicionais") or {}
    consulta = consulta_artifact.get("consulta", "").strip()

    if not consulta:
        raise ValueError(
            "Não foi encontrada a consulta do Worker 5 no Blackboard."
        )

    # Recupera os trechos do ChromaDB sem bloquear o event loop do LangGraph.
    retriever = RAGRetriever()
    trechos = await asyncio.to_thread(retriever.buscar, consulta, 10)

    conhecimento_recuperado = json.dumps(
        trechos,
        ensure_ascii=False,
        indent=2,
    )

    # Passa somente os artefatos da Visão necessários ao Worker 6.
    artefatos_visao = json.dumps(
        {
            "escopo": visao.get("escopo"),
            "posicionamento": visao.get("posicionamento"),
            "stakeholders": visao.get("stakeholders"),
            "necessidades_funcionalidades": visao.get(
                "necessidades_funcionalidades"
            ),
        },
        ensure_ascii=False,
        indent=2,
    )

    resultado = await b.DevelopAdditionalExplainabilityRequirements(
        artefatos_visao=artefatos_visao,
        consulta_worker5=consulta,
        conhecimento_recuperado=conhecimento_recuperado,
    )

    requisitos = [
        item.model_dump() if hasattr(item, "model_dump") else item
        for item in resultado
    ]

    blackboard = deepcopy(state["blackboard"])
    blackboard["visao_explicabilidade"]["conhecimento_recuperado"] = {
        "consulta": consulta,
        "quantidade_trechos": len(trechos),
        "trechos": trechos,
    }
    blackboard["visao_explicabilidade"][
        "requisitos_adicionais_explicabilidade"
    ] = {
        "requisitos": requisitos
    }

    print(f"\\nTrechos recuperados pelo RAG: {len(trechos)}")
    print("\\n=== RESULTADO DO WORKER 6 ===")
    print(json.dumps(requisitos, ensure_ascii=False, indent=2))

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
    # 5. Requisitos Adicionais relacionados à Explicabilidade
    # --------------------------------------------------------

    doc += """---

## 5. Requisitos Adicionais relacionados à Explicabilidade

"""

    adicionais_artifact = visao.get(
        "requisitos_adicionais_explicabilidade"
    ) or {}
    requisitos_adicionais = adicionais_artifact.get("requisitos", [])

    if requisitos_adicionais:
        for i, requisito in enumerate(requisitos_adicionais, start=1):
            doc += f"""### 5.{i} {texto_md(requisito.get("categoria"), "Categoria não identificada")}

**Requisito:** {texto_md(requisito.get("requisito"))}

**Justificativa:** {texto_md(requisito.get("justificativa"))}

"""
    else:
        doc += (
            "Nenhum requisito adicional fundamentado foi identificado "
            "pelas evidências recuperadas até o momento. "
            "Isso não significa necessariamente que não existam requisitos; "
            "pode ser necessária investigação adicional.\\n\\n"
        )

    # --------------------------------------------------------
    # Observação sobre o estado do documento
    # --------------------------------------------------------

    doc += """---

## Observações sobre o documento

Este documento foi compilado a partir dos artefatos produzidos
pelos Workers 1 a 6 da etapa Visão do OpenUPExp.

Os requisitos adicionais da Seção 5 devem ser analisados pelo
Engenheiro de Requisitos. Sua fundamentação depende dos trechos
recuperados pelo RAG e da relação com as necessidades identificadas
na Visão. Os resultados gerados não substituem a validação humana.

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
builder.add_node("worker_5", worker_5)
builder.add_node("worker_6", worker_6)

builder.add_edge(START, "worker_1")
builder.add_edge("worker_1", "worker_2")
builder.add_edge("worker_2", "worker_3")
builder.add_edge("worker_3", "worker_4")
builder.add_edge("worker_4", "worker_5")
builder.add_edge("worker_5", "worker_6")
builder.add_edge("worker_6", END)

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
