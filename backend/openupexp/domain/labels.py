"""Nomes legíveis dos itens (STK-01 -> "Solicitante MEI") para a tela e os documentos.

O código continua sendo a referência de rastreabilidade; o nome só ajuda a leitura.
"""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES
from openupexp.db.models import Run
from openupexp.domain import artifacts as store

ITEM_ID = re.compile(r"^[A-Z]{2,4}-\d+$")
MAX_LEN = 70

# Campo que dá nome a cada item, pelo prefixo do ID.
NAME_FIELD = {
    "STK": "nome", "SN": "solicitacao", "DT": "termo", "TERM": "termo", "NEED": "necessidade",
    "POS": "para_quem", "CR": "requisito", "RN": "necessidade", "RI": "enunciado", "RC": "requisito",
    "REQ": "enunciado", "HU": "quero",
}


def short(text: str, n: int = MAX_LEN) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip(" ,.;:") + "…"


def label_index(*contents: dict[str, dict]) -> dict[str, str]:
    """ID -> nome completo, a partir do conteúdo das partes; o primeiro conteúdo prevalece."""
    out: dict[str, str] = {}
    for content in contents:
        for atype, value in content.items():
            at = ARTIFACT_TYPES.get(atype)
            if not at or not at.list_field or not isinstance(value, dict):
                continue
            for item in value.get(at.list_field) or []:
                key, name = item.get("id"), item.get(NAME_FIELD.get(at.prefix or "", ""))
                if key and name and key not in out:
                    out[key] = " ".join(str(name).split())
    # o plano de elicitação é nomeado pelo stakeholder
    for content in contents:
        for item in (content.get("elicitation.plan") or {}).get("itens") or []:
            if item.get("id") and item.get("id") not in out and item.get("stakeholder_id") in out:
                out[item["id"]] = f"Conversa com {out[item['stakeholder_id']]}"
    return out


def ref(index: dict[str, str], key) -> str:
    """'Solicitante MEI (STK-01)'; sem nome conhecido, o próprio código."""
    if not isinstance(key, str) or not ITEM_ID.match(key) or key not in index:
        return "" if key is None else str(key)
    return f"{short(index[key])} ({key})"


def refs(index: dict[str, str], keys) -> str:
    return "; ".join(ref(index, k) for k in keys or [])


async def run_index(session: AsyncSession, run: Run) -> dict[str, str]:
    """Índice da execução e das suas bases (a Fase 2 também cita itens da Visão)."""
    contents = [{t: v.content for t, v in (await store.current_versions(session, run.id)).items()}]
    for base_id in await store.lineage(session, run):
        contents.append({t: v.content for t, v in (await store.current_versions(session, base_id)).items()})
    return label_index(*contents)


# Valores das listas fechadas dos contratos, com nome legível (fases 1 e 2; os demais seguem a regra geral).
VALUE_LABELS = {
    # técnicas de elicitação
    "ENTREVISTA": "Entrevista", "WORKSHOP": "Workshop", "OBSERVACAO": "Observação",
    "ANALISE_DOCUMENTAL": "Análise documental", "PROTOTIPO": "Protótipo", "OUTRA": "Outra",
    # objetivos da explicação (passo 3 de encontrar-descrever-requisitos.md)
    "COMPREENSAO": "Compreensão", "JUSTIFICATIVA": "Justificativa", "TRANSPARENCIA": "Transparência",
    "RASTREABILIDADE": "Rastreabilidade", "AUDITORIA": "Auditoria",
    "CONFORMIDADE_REGULATORIA": "Conformidade regulatória", "CONFIANCA": "Confiança", "OUTRO": "Outro",
    "CONTESTACAO": "Contestação", "APRENDIZADO": "Aprendizado",
    # tipo de requisito
    "EXPLICABILIDADE": "Explicabilidade", "COMPLEMENTAR": "Complementar",
    # categorias da seção 5
    "NORMAS_REGULAMENTOS": "Padrões, normas e regulamentos", "PLATAFORMA_DESEMPENHO": "Plataforma, hardware e desempenho",
    "QUALIDADE_EXPLICACOES": "Qualidade das explicações", "RESTRICOES_DEPENDENCIAS": "Restrições, dependências e assunções",
    "DOCUMENTACAO_SUPORTE": "Documentação e suporte",
    # tipo de evidência
    "OBRIGACAO_NORMATIVA": "Exigência legal", "RECOMENDACAO_TECNICA": "Recomendação técnica",
    "DERIVADO_VISAO": "Vem da Visão", "ELICITACAO": "Conversa com as pessoas", "VISAO": "Pedido registrado na Visão",
    # risco e prioridade
    "ALTO": "Alto", "MEDIO": "Médio", "BAIXO": "Baixo",
}
_ENUM = re.compile(r"^[A-Z][A-Z_]+$")


VERIFICATION_LABELS = {"verified": "citação conferida", "unverified_quote": "citação não encontrada na fonte",
                       "source_not_provided": "fonte não informada"}


def value_label(value) -> str:
    """'COMPREENSAO' -> 'Compreensão'; texto comum fica como está."""
    if isinstance(value, str) and value in VERIFICATION_LABELS:
        return VERIFICATION_LABELS[value]
    if not isinstance(value, str) or not _ENUM.match(value):
        return "" if value is None else str(value)
    return VALUE_LABELS.get(value) or value.replace("_", " ").capitalize()


def resolved_gaps(contents: dict[str, dict], index: dict[str, str]) -> list[tuple[str, dict]]:
    """Lacunas respondidas pelo Engenheiro (campo lacunas_resolvidas), com a parte e o item de origem."""
    out: list[tuple[str, dict]] = []
    for atype, value in contents.items():
        at = ARTIFACT_TYPES.get(atype)
        if not at or not isinstance(value, dict):
            continue
        out += [(at.title, g) for g in value.get("lacunas_resolvidas") or []]
        for item in (value.get(at.list_field) or []) if at.list_field else []:
            out += [(f"{at.title} · {ref(index, item.get('id'))}", g) for g in item.get("lacunas_resolvidas") or []]
    return out
