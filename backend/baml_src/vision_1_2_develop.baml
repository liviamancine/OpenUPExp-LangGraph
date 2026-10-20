// Subprocesso 1.2 Develop Explainability Vision
// Contratos derivados dos workers W2/W4/W5/W6 originais (legado).

// ---------------------------------------------------------------------------
// 1.2.1 Identify Explainability Needs  (evolução do W4 MapExplainabilityNeeds)
// ---------------------------------------------------------------------------

class ExplainabilityNeed {
  id string? @description("NEED-n existente; null se nova")
  necessidade string @description("Necessidade de explicabilidade em nível conceitual (o quê e por quê, não o como)")
  stakeholder_ids string[] @description("IDs STK-n relacionados")
  solicitacao_ids string[] @description("IDs SN-n que sustentam a necessidade")
  prioridade string? @description("Somente se explicitamente indicada na entrada; caso contrário null")
  planned_release string? @description("Somente se explicitamente indicada na entrada; caso contrário null")
  aspecto_associado string? @description("Opcional (decisão A-06 pendente); somente se a entrada sustentar")
  lacunas Lacuna[]
}

class ExplainabilityNeedsArtifact {
  necessidades ExplainabilityNeed[]
}

class IdentifyNeedsInput {
  stakeholders Stakeholder[]
  solicitacoes StakeholderNeed[]
  glossario GlossaryTerm[]
  necessidades_existentes ExplainabilityNeed[]
}

function IdentifyExplainabilityNeeds(entrada: IdentifyNeedsInput, contexto: ContextItem[]) -> ExplainabilityNeedsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.2.1 "Identify Explainability Needs" do OpenUPExp: transformar as
    solicitações dos stakeholders em necessidades de explicabilidade em nível conceitual.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("NEED") }}

    REGRAS ESPECÍFICAS
    - Cada necessidade deve citar os SN-n que a sustentam e os STK-n envolvidos.
    - Agrupe solicitações equivalentes somente sem perder distinções relevantes.
    - Não transforme necessidades em funcionalidades, mecanismos, algoritmos ou métricas.
    - Prioridade e release: null quando não houver evidência explícita (registre Lacuna).
    - Se não houver evidência suficiente, retorne a lista vazia.

    {{ _.role("user") }}
    STAKEHOLDERS
    {{ entrada.stakeholders }}

    SOLICITAÇÕES DOS STAKEHOLDERS (1.1.3)
    {{ entrada.solicitacoes }}

    GLOSSÁRIO
    {{ entrada.glossario }}

    NECESSIDADES EXISTENTES (preserve os IDs)
    {{ entrada.necessidades_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// Posicionamento (template §2.2) — sem tarefa BPMN (A-03)
// Evolução do W2 GenerateExplainabilityPositioning
// ---------------------------------------------------------------------------

class Positioning {
  id string? @description("POS-n existente; null se novo")
  stakeholder_id string
  para_quem string
  para_que string
  nome_produto string?
  categoria_produto string?
  beneficio_chave string?
  unlike string? @description("Alternativa de referência; null se não estiver na entrada")
  our_product string?
  need_ids string[]
  lacunas Lacuna[]
}

class PositioningArtifact {
  posicionamentos Positioning[]
}

class PositioningInput {
  problema ExplainabilityProblem
  stakeholders Stakeholder[]
  necessidades ExplainabilityNeed[]
  posicionamentos_existentes Positioning[]
}

function GenerateExplainabilityPositioning(entrada: PositioningInput, contexto: ContextItem[]) -> PositioningArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você elabora a Declaração de Posicionamento da Explicabilidade (template da Visão §2.2) do
    OpenUPExp, uma por perfil de stakeholder que necessita de explicabilidade.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("POS") }}

    REGRAS ESPECÍFICAS
    - Exatamente um posicionamento para cada stakeholder da entrada (use o STK-n em stakeholder_id).
    - Relacione as necessidades (NEED-n) que justificam o posicionamento.
    - Campos sem evidência (ex.: unlike, beneficio_chave): null + Lacuna para o Engenheiro.

    {{ _.role("user") }}
    PROBLEMA
    {{ entrada.problema }}

    STAKEHOLDERS
    {{ entrada.stakeholders }}

    NECESSIDADES DE EXPLICABILIDADE
    {{ entrada.necessidades }}

    POSICIONAMENTOS EXISTENTES (preserve os IDs)
    {{ entrada.posicionamentos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 1.2.2 Identify Complementary Requirements
//   PlanReferenceQueries (evolução do W5) + recuperação híbrida (determinística)
//   + DevelopComplementaryRequirements (evolução do W6, com evidência tipada — P-03)
// ---------------------------------------------------------------------------

enum ComplementaryCategory {
  NORMAS_REGULAMENTOS @description("§5.1 Padrões, Normas e Regulamentos Aplicáveis")
  PLATAFORMA_DESEMPENHO @description("§5.2 Plataforma, Hardware e Desempenho")
  QUALIDADE_EXPLICACOES @description("§5.3 Qualidade das Explicações")
  RESTRICOES_DEPENDENCIAS @description("§5.4 Restrições de Design, Dependências e Assunções")
  DOCUMENTACAO_SUPORTE @description("§5.5 Documentação e Suporte")
}

class ReferenceQuery {
  secao ComplementaryCategory
  consulta string @description("Consulta curta e objetiva para recuperação")
  tipos_fonte string[] @description("Subconjunto de: lei, manual, academico")
  referencias_explicitas string[] @description("Referências normativas citadas na entrada, ex.: 'Lei 13.709 art. 20'")
}

class ReferenceQueryPlan {
  consultas ReferenceQuery[]
}

class PlanQueriesInput {
  problema ExplainabilityProblem
  necessidades ExplainabilityNeed[]
}

function PlanReferenceQueries(entrada: PlanQueriesInput, contexto: ContextItem[]) -> ReferenceQueryPlan {
  client OpenUPExpCheap
  prompt #"
    {{ _.role("system") }}
    Você planeja consultas à Explainability Reference Base (normas, leis, manuais, literatura)
    para a seção 5 — Requisitos Adicionais relacionados à Explicabilidade — do Documento de Visão.

    REGRAS
    - Gere de 3 a 8 consultas curtas, cada uma focada numa subseção (5.1 a 5.5) pertinente.
    - Use o domínio e as necessidades das entradas; não invente normas.
    - 'referencias_explicitas' só pode conter referências normativas que aparecem literalmente
      nas entradas. Caso contrário, lista vazia.
    - Não defina prioridades nem releases.

    {{ _.role("user") }}
    PROBLEMA
    {{ entrada.problema }}

    NECESSIDADES DE EXPLICABILIDADE
    {{ entrada.necessidades }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

class ComplementaryRequirement {
  id string? @description("CR-n existente; null se novo")
  categoria ComplementaryCategory
  requisito string
  justificativa string @description("Relação entre a necessidade da Visão e a evidência")
  need_ids string[] @description("Necessidades da Visão relacionadas (obrigatório)")
  evidencias EvidenceRef[] @description("Pelo menos uma; sem evidência, não produza o requisito")
}

class ComplementaryRequirementsArtifact {
  requisitos ComplementaryRequirement[]
}

class ComplementaryInput {
  problema ExplainabilityProblem
  necessidades ExplainabilityNeed[]
  requisitos_existentes ComplementaryRequirement[]
}

function DevelopComplementaryRequirements(entrada: ComplementaryInput, contexto: ContextItem[]) -> ComplementaryRequirementsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.2.2 "Identify Complementary Requirements" do OpenUPExp: elaborar
    requisitos adicionais relacionados à explicabilidade (Visão §5.1–5.5), fundamentados
    nos trechos da Explainability Reference Base fornecidos no contexto (origem 'retrieved').

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("CR") }}

    VALIDAÇÃO OBRIGATÓRIA DAS EVIDÊNCIAS
    1. Cada requisito deve ser complementar a pelo menos uma necessidade (need_ids).
    2. Antes de elaborar um requisito, identifique o trecho exato que o sustenta. Em
       'evidencias', use a 'referencia' do item de contexto e copie a 'citacao' LITERALMENTE.
       Citações são verificadas mecanicamente contra o texto da fonte.
    3. Verifique se o trecho se aplica ao domínio e à situação. Não generalize uma obrigação
       prevista para um contexto específico.
    4. Diferencie o tipo: OBRIGACAO_NORMATIVA, RECOMENDACAO_TECNICA ou DERIVADO_VISAO.
    5. Não afirme que uma lei exige uma funcionalidade se o trecho não estabelece essa obrigação.
    6. Não infira requisitos apenas da existência de uma autoridade reguladora ou de
       princípios gerais.
    7. Não detalhe implementação, não atribua prioridade nem release.
    8. Não crie requisitos apenas para preencher categorias. Sem evidência suficiente,
       descarte o requisito. Retorne lista vazia se nenhum for fundamentado.

    {{ _.role("user") }}
    PROBLEMA
    {{ entrada.problema }}

    NECESSIDADES DE EXPLICABILIDADE
    {{ entrada.necessidades }}

    REQUISITOS COMPLEMENTARES EXISTENTES (preserve os IDs)
    {{ entrada.requisitos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 1.2.3 Define Explainability Scope and Limits (checklist do DRE)
// ---------------------------------------------------------------------------

class ChecklistQuestion {
  dimensao string
  pergunta string
}

class LimitAnswer {
  dimensao string
  pergunta string @description("Pergunta do checklist, literal")
  resposta string? @description("Resposta sustentada pelas entradas; null se não houver evidência")
  baseada_em OrigemRef[]
  lacuna Lacuna?
}

class ExplainabilityLimitsArtifact {
  respostas LimitAnswer[]
}

class LimitsInput {
  stakeholders Stakeholder[]
  necessidades ExplainabilityNeed[]
  requisitos_complementares ComplementaryRequirement[]
  checklist ChecklistQuestion[]
}

function DefineExplainabilityLimits(entrada: LimitsInput, contexto: ContextItem[]) -> ExplainabilityLimitsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.2.3 "Define Explainability Scope and Limits" do OpenUPExp,
    respondendo ao checklist "Limite da Explicabilidade".

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Responda TODAS as perguntas do checklist, na mesma ordem, copiando 'dimensao' e 'pergunta'.
    - Sem evidência para responder, 'resposta' = null e preencha 'lacuna' com a pergunta
      que o Engenheiro deve levar aos stakeholders.
    - 'baseada_em' deve citar os IDs (STK-n, NEED-n, CR-n) que sustentam a resposta.

    {{ _.role("user") }}
    CHECKLIST
    {{ entrada.checklist }}

    STAKEHOLDERS
    {{ entrada.stakeholders }}

    NECESSIDADES
    {{ entrada.necessidades }}

    REQUISITOS COMPLEMENTARES
    {{ entrada.requisitos_complementares }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}
