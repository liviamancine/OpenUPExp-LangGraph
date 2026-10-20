// Subprocesso 2.1 Prepare Explainability Elicitation
// O template do Plano de Elicitação ainda não existe na teoria (A-14). Os campos abaixo são
// uma interpretação provisória derivada de tarefas/encontrar-descrever-requisitos.md (passo 1)
// e da anotação BPMN "Explainability Elicitation Strategy".

// Técnicas citadas no passo 1 de encontrar-descrever-requisitos.md
enum ElicitationTechnique {
  ENTREVISTA
  WORKSHOP
  OBSERVACAO @description("Observação de atividades")
  ANALISE_DOCUMENTAL
  PROTOTIPO
  OUTRA @description("Outra técnica adequada ao contexto; justifique no objetivo")
}

class ElicitationPlanItem {
  id string? @description("EP-n existente; null se novo")
  stakeholder_id string @description("STK-n do stakeholder a ser ouvido")
  objetivo string @description("O que se quer compreender com este stakeholder sobre as decisões do sistema")
  tecnicas ElicitationTechnique[]
  perguntas string[] @description("Roteiro de perguntas sobre necessidades de explicação (não sobre soluções)")
  need_ids string[] @description("Necessidades da Visão (NEED-n) que a elicitação deve aprofundar")
  lacunas_alvo string[] @description("Lacunas da Visão que esta elicitação tenta resolver (texto literal da lacuna)")
  lacunas Lacuna[]
}

class ElicitationPlanArtifact {
  itens ElicitationPlanItem[]
}

class PlanElicitationInput {
  stakeholders Stakeholder[]
  necessidades ExplainabilityNeed[]
  lacunas_visao string[] @description("Lacunas abertas da Visão aprovada")
  plano_existente ElicitationPlanItem[]
}

function PlanElicitation(entrada: PlanElicitationInput, contexto: ContextItem[]) -> ElicitationPlanArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 2.1.2 "Explainability Elicitation Plan" do OpenUPExp: planejar a
    elicitação das necessidades de explicabilidade a partir da Visão aprovada.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("EP") }}

    REGRAS ESPECÍFICAS
    - Exatamente um item de plano para cada stakeholder da entrada (use o STK-n em stakeholder_id).
    - As perguntas investigam QUAIS decisões precisam ser explicadas, PARA QUEM, EM QUE CONTEXTO
      e com qual OBJETIVO (compreensão, justificativa, auditoria, conformidade, confiança…).
      Não pergunte sobre técnicas de explicação nem sobre soluções.
    - Priorize perguntas que resolvam as lacunas da Visão; cite-as em lacunas_alvo.
    - Escolha técnicas compatíveis com o stakeholder; o Engenheiro de Requisitos ajusta o plano.

    {{ _.role("user") }}
    STAKEHOLDERS
    {{ entrada.stakeholders }}

    NECESSIDADES DE EXPLICABILIDADE DA VISÃO
    {{ entrada.necessidades }}

    LACUNAS ABERTAS DA VISÃO
    {{ entrada.lacunas_visao }}

    PLANO EXISTENTE (preserve os IDs)
    {{ entrada.plano_existente }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}
