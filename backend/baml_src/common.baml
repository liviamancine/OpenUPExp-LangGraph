// Tipos comuns (docs/architecture/08-contratos-baml.md §8.2)

class Lacuna {
  campo string @description("Nome do campo que não pôde ser preenchido")
  motivo string @description("Por que a informação não está nas entradas")
  pergunta_sugerida string? @description("Pergunta que o Engenheiro de Requisitos pode fazer aos stakeholders")
}

class ContextItem {
  origem string @description("required | digest | retrieved | related | feedback | document")
  referencia string @description("Referência estável do material")
  conteudo string
}

enum EvidenceKind {
  OBRIGACAO_NORMATIVA @description("O trecho estabelece obrigação legal ou normativa aplicável ao contexto")
  RECOMENDACAO_TECNICA @description("O trecho recomenda, mas não obriga")
  DERIVADO_VISAO @description("O requisito decorre de uma necessidade da Visão; o trecho apenas contextualiza")
}

class EvidenceRef {
  chunk_ref string @description("Exatamente o valor de referencia de um item de contexto com origem 'retrieved'")
  citacao string @description("Trecho LITERAL copiado do conteúdo desse item, sem reescrever")
  tipo EvidenceKind
}

class OrigemRef {
  referencia string @description("ID de item de entrada (ex.: STK-02, NEED-01) ou 'escopo'")
  relacao string @description("Como a saída decorre desta entrada")
}

template_string RegrasNaoInvencao() #"
REGRAS DE RIGOR (NÃO INVENÇÃO)
1. Baseie-se EXCLUSIVAMENTE nas entradas fornecidas. Não use conhecimento externo.
2. Não apresente inferências, hipóteses ou exemplos como fatos confirmados.
3. Preserve exatamente os nomes, termos e domínios mencionados nas entradas.
4. Quando uma informação não estiver nas entradas, deixe o campo vazio/nulo e registre
   uma Lacuna explicando o motivo. Nunca complete lacunas por inferência.
5. Não proponha técnicas, algoritmos, ferramentas ou arquiteturas que não estejam nas entradas.
6. Não tome decisões que competem ao Engenheiro de Requisitos (prioridade, release,
   aprovação) sem evidência explícita nas entradas.
"#

template_string RegrasIds(prefixo: string) #"
IDENTIFICADORES
- Itens já existentes foram fornecidos com seus IDs ({{ prefixo }}-n). Se um item de saída
  corresponde a um item existente, devolva o MESMO id.
- Para itens novos, deixe o campo id como null; o sistema atribuirá o ID.
"#

template_string ContextoAdicional(contexto: ContextItem[]) #"
{% if contexto|length > 0 %}
MATERIAL DE CONTEXTO ADICIONAL
{% for c in contexto %}
--- [{{ c.origem }}] {{ c.referencia }}{% if c.origem == "feedback" %}  <<< FEEDBACK DO REVISOR HUMANO: tem precedência; corrija a saída de acordo com ele, mantendo as regras de não invenção >>>{% endif %}
{{ c.conteudo }}
{% endfor %}
{% endif %}
"#
