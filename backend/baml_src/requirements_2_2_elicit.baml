// Subprocesso 2.2 Elicit Explainability Requirements
// Formatos provisórios (A-14): o template de requisito de explicabilidade ainda não existe na
// teoria. Os objetivos de explicação vêm do passo 3 de tarefas/encontrar-descrever-requisitos.md.

// Objetivos citados no passo 3 de encontrar-descrever-requisitos.md (lista provisória, A-15)
enum ExplanationGoal {
  COMPREENSAO
  JUSTIFICATIVA
  TRANSPARENCIA
  RASTREABILIDADE
  AUDITORIA
  CONFORMIDADE_REGULATORIA
  CONFIANCA
  OUTRO @description("Outro objetivo; descreva no enunciado")
}

class ElicitationEvidence {
  fonte_ref string @description("Exatamente a referencia de um item de contexto 'retrieved' (chunk:...) ou um SN-n da Visão")
  citacao string @description("Trecho LITERAL copiado da fonte, sem reescrever")
}

// ---------------------------------------------------------------------------
// 2.2.1 Obtain Explainability Needs — executada por stakeholder (map)
// ---------------------------------------------------------------------------

class ElicitedNeed {
  id string? @description("RN-n existente; null se nova")
  stakeholder_id string
  necessidade string @description("Necessidade de explicação expressa pelo stakeholder, em suas palavras")
  decisao_alvo string? @description("Decisão, recomendação ou previsão do sistema que precisa ser explicada")
  objetivo ExplanationGoal?
  need_ids string[] @description("NEED-n da Visão que esta necessidade aprofunda; vazio se for nova")
  evidencias ElicitationEvidence[] @description("Pelo menos uma; sem evidência, não produza a necessidade")
  lacunas Lacuna[]
}

class ElicitedNeedsArtifact {
  necessidades ElicitedNeed[]
}

class ExtractNeedsInput {
  stakeholder Stakeholder
  plano ElicitationPlanItem?
  solicitacoes_visao StakeholderNeed[] @description("Solicitações deste stakeholder registradas na Visão (1.1.3)")
  necessidades_visao ExplainabilityNeed[]
  necessidades_existentes ElicitedNeed[]
}

function ExtractElicitedNeeds(entrada: ExtractNeedsInput, contexto: ContextItem[]) -> ElicitedNeedsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 2.2.1 "Obtain Explainability Needs" do OpenUPExp para UM stakeholder:
    extrair, do material de elicitação, as necessidades de explicação que ele expressou.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("RN") }}

    REGRAS ESPECÍFICAS
    - Considere apenas o que este stakeholder disse ou o que o material atribui a ele.
    - Cada necessidade precisa de evidência: copie a citação literal do trecho recuperado
      (fonte_ref = referencia do item 'retrieved') ou da solicitação da Visão (fonte_ref = SN-n).
    - Relacione a NEED-n da Visão quando a necessidade a aprofunda; necessidades novas ficam com
      need_ids vazio e são igualmente importantes.
    - Registre conflitos, dúvidas e expectativas divergentes como Lacuna.
    - Se o material não trouxer nada sobre este stakeholder, retorne a lista vazia.

    {{ _.role("user") }}
    STAKEHOLDER
    {{ entrada.stakeholder }}

    PLANO DE ELICITAÇÃO PARA ESTE STAKEHOLDER
    {{ entrada.plano }}

    SOLICITAÇÕES REGISTRADAS NA VISÃO
    {{ entrada.solicitacoes_visao }}

    NECESSIDADES DA VISÃO
    {{ entrada.necessidades_visao }}

    NECESSIDADES JÁ ELICITADAS (preserve os IDs)
    {{ entrada.necessidades_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 2.2.2 Identify Explainability Requirements — executada por necessidade da Visão (map)
// ---------------------------------------------------------------------------

class ExplainabilityRequirement {
  id string? @description("RI-n existente; null se novo")
  enunciado string @description("O sistema deve ... (o QUÊ explicar, para QUEM, em que SITUAÇÃO; não o COMO)")
  stakeholder_ids string[]
  need_ids string[] @description("NEED-n da Visão atendidas")
  rn_ids string[] @description("RN-n que sustentam o requisito (obrigatório)")
  objetivo ExplanationGoal
  decisao_alvo string?
  contexto_de_uso string?
  lacunas Lacuna[]
}

class ExplainabilityRequirementsArtifact {
  requisitos ExplainabilityRequirement[]
}

class IdentifyRequirementsInput {
  necessidade ExplainabilityNeed? @description("Necessidade da Visão em foco; null para necessidades elicitadas novas")
  necessidades_elicitadas ElicitedNeed[] @description("RN-n a transformar em requisitos; TODAS devem ser usadas")
  stakeholders Stakeholder[]
  glossario GlossaryTerm[]
  requisitos_existentes ExplainabilityRequirement[]
}

function IdentifyExplainabilityRequirements(entrada: IdentifyRequirementsInput, contexto: ContextItem[]) -> ExplainabilityRequirementsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 2.2.2 "Identify Explainability Requirements" do OpenUPExp: transformar
    necessidades elicitadas em requisitos de explicabilidade em nível estratégico.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("RI") }}

    REGRAS ESPECÍFICAS
    - Toda necessidade elicitada (RN-n) da entrada deve aparecer em rn_ids de pelo menos um requisito.
    - O enunciado diz O QUE precisa ser explicado, PARA QUEM e EM QUE SITUAÇÃO. Conteúdo, formato,
      mecanismos e níveis de explicação são detalhados em fases posteriores: não os defina aqui.
    - Use os termos do glossário.
    - Requisitos de stakeholders diferentes com objetivos diferentes ficam separados.

    {{ _.role("user") }}
    NECESSIDADE DA VISÃO EM FOCO
    {{ entrada.necessidade }}

    NECESSIDADES ELICITADAS
    {{ entrada.necessidades_elicitadas }}

    STAKEHOLDERS
    {{ entrada.stakeholders }}

    GLOSSÁRIO
    {{ entrada.glossario }}

    REQUISITOS EXISTENTES (preserve os IDs)
    {{ entrada.requisitos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 2.2.3 Identify Complementary Requirements — refina os CR-n da Visão (interpretação de A-18)
// ---------------------------------------------------------------------------

class PhaseComplementaryRequirement {
  id string? @description("RC-n existente; null se novo")
  categoria ComplementaryCategory
  requisito string
  justificativa string
  ri_ids string[] @description("Requisitos de explicabilidade (RI-n) afetados (obrigatório)")
  cr_ids string[] @description("CR-n da Visão que este requisito refina; vazio se novo")
  evidencias EvidenceRef[] @description("Pelo menos uma; sem evidência, não produza o requisito")
}

class PhaseComplementaryArtifact {
  requisitos PhaseComplementaryRequirement[]
}

class RefineComplementaryInput {
  requisitos ExplainabilityRequirement[]
  requisitos_complementares_visao ComplementaryRequirement[]
  requisitos_existentes PhaseComplementaryRequirement[]
}

function RefineComplementaryRequirements(entrada: RefineComplementaryInput, contexto: ContextItem[]) -> PhaseComplementaryArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 2.2.3 "Identify Complementary Requirements" do OpenUPExp: identificar
    restrições, dependências e requisitos complementares (normas, desempenho, privacidade,
    auditoria, documentação) que influenciam os requisitos de explicabilidade elicitados.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("RC") }}

    REGRAS ESPECÍFICAS
    - Parta dos requisitos complementares da Visão (CR-n): refine-os à luz dos requisitos
      elicitados (RI-n) e registre o CR-n refinado em cr_ids.
    - Requisitos novos só com evidência na base de referência recuperada.
    - Cada requisito aponta os RI-n afetados.
    - Evidência: chunk_ref = referencia exata de um item 'retrieved'; citacao = trecho literal.

    {{ _.role("user") }}
    REQUISITOS DE EXPLICABILIDADE ELICITADOS
    {{ entrada.requisitos }}

    REQUISITOS COMPLEMENTARES DA VISÃO
    {{ entrada.requisitos_complementares_visao }}

    REQUISITOS EXISTENTES (preserve os IDs)
    {{ entrada.requisitos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 2.2.4 Organize and Consolidate Requirements
// ---------------------------------------------------------------------------

enum RequirementKind {
  EXPLICABILIDADE
  COMPLEMENTAR
}

class ConsolidatedRequirement {
  id string? @description("REQ-n existente; null se novo")
  enunciado string
  tipo RequirementKind
  objetivo ExplanationGoal?
  categoria ComplementaryCategory? @description("Somente para tipo COMPLEMENTAR")
  stakeholder_ids string[]
  need_ids string[]
  origem_ids string[] @description("RI-n e RC-n consolidados neste requisito (obrigatório)")
  justificativa_agrupamento string? @description("Por que itens foram fundidos; null se não houve fusão")
  lacunas Lacuna[]
}

class DiscardedItem {
  origem_id string @description("RI-n ou RC-n não incorporado")
  motivo string @description("Ex.: duplicado de REQ-n, fora do escopo da Visão")
}

class ConsolidatedRequirementsArtifact {
  requisitos ConsolidatedRequirement[]
  descartados DiscardedItem[]
}

class SimilarPair {
  a string
  b string
  similaridade float
}

class ConsolidateInput {
  requisitos ExplainabilityRequirement[]
  complementares PhaseComplementaryRequirement[]
  pares_similares SimilarPair[] @description("Candidatos a duplicidade calculados por similaridade semântica")
  consolidados_existentes ConsolidatedRequirement[]
}

function ConsolidateRequirements(entrada: ConsolidateInput, contexto: ContextItem[]) -> ConsolidatedRequirementsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 2.2.4 "Organize and Consolidate Requirements" do OpenUPExp: organizar
    os requisitos elicitados e complementares num conjunto consolidado, sem perder nenhum.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("REQ") }}

    REGRAS ESPECÍFICAS
    - TODO RI-n e RC-n da entrada aparece em origem_ids de um requisito consolidado OU em descartados.
    - Funda apenas itens realmente equivalentes (os pares_similares são candidatos, não certezas);
      explique a fusão em justificativa_agrupamento.
    - Ao fundir, preserve a união de stakeholders, necessidades e objetivos.
    - Descarte só com motivo explícito (duplicidade ou fora do escopo da Visão).
    - Não reescreva o sentido dos requisitos; padronize apenas a redação ("O sistema deve...").

    {{ _.role("user") }}
    REQUISITOS DE EXPLICABILIDADE (RI)
    {{ entrada.requisitos }}

    REQUISITOS COMPLEMENTARES (RC)
    {{ entrada.complementares }}

    CANDIDATOS A DUPLICIDADE
    {{ entrada.pares_similares }}

    CONSOLIDADOS EXISTENTES (preserve os IDs)
    {{ entrada.consolidados_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}
