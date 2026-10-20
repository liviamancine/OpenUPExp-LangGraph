// Fase 4 — Define Explainability Specification
// Passos de OpenUPExp/tarefas/especificar-requisitos.md (1–4). A teoria não traz template para
// HU, critérios de aceitação e características da explicação (o DRE só tem a Visão e o
// Glossário); os formatos abaixo seguem os "formatos recomendados" e as listas dos passos
// (provisório, A-14/A-21), ver docs/architecture/12-decisoes-pendentes.md §12.6.

// ---------------------------------------------------------------------------
// Características da explicação (passo 3; momento e forma também no checklist de limites)
// ---------------------------------------------------------------------------

enum ExplanationDetailLevel {
  RESUMIDO
  INTERMEDIARIO
  DETALHADO
}

enum ExplanationFormat {
  TEXTUAL
  VISUAL
  TABULAR
  COMBINADO
}

enum ExplanationMoment {
  ANTES @description("Antes da decisão")
  DURANTE @description("Durante a decisão")
  APOS @description("Após a decisão")
  SOB_DEMANDA @description("Quando solicitada pelo stakeholder")
}

// Ficha de entrada por requisito, montada deterministicamente em 4.1.2 a partir da Análise.
class SpecificationPlanEntry {
  req_id string
  enunciado string
  prioridade string? @description("MoSCoW aprovado na Fase 3")
  stakeholder_ids string[]
  need_ids string[]
  aspecto_predominante string?
  tipos_explicacao string[]
  contexto_uso string?
  decisao_apoiada string?
  objetivo_principal string?
  restricoes string[] @description("Restrições da Fase 3 (tipo: descrição)")
}

// ---------------------------------------------------------------------------
// 4.2.1 Specify Requirements — Histórias de Usuário, em lotes de requisitos
// ---------------------------------------------------------------------------

class UserStory {
  id string? @description("HU-n existente; null se nova")
  req_id string @description("REQ-n especificado pela história")
  stakeholder_id string @description("STK-n do 'Como'")
  como string @description("Nome do stakeholder, como está na entrada")
  quero string @description("Necessidade de explicabilidade, sem detalhes de implementação")
  para string @description("Benefício esperado")
  lacunas Lacuna[]
}

class UserStoriesArtifact {
  historias UserStory[]
}

class SpecifyStoriesInput {
  requisitos SpecificationPlanEntry[]
  stakeholders Stakeholder[]
  historias_existentes UserStory[]
}

function SpecifyUserStories(entrada: SpecifyStoriesInput, contexto: ContextItem[]) -> UserStoriesArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 4.2.1 "Specify Requirements" do OpenUPExp: especificar cada requisito de
    explicabilidade como História de Usuário (HU), sob a perspectiva do stakeholder.

    {{ RegrasNaoInvencao() }}

    {{ RegrasIds("HU") }}

    REGRAS ESPECÍFICAS
    - Formato: Como <stakeholder> / Quero <necessidade de explicabilidade> / Para <benefício esperado>.
    - Pelo menos uma HU por requisito da entrada (req_id = REQ-n). Uma HU expressa UMA necessidade
      principal; se o requisito atende stakeholders com necessidades distintas, escreva uma HU por
      stakeholder (stakeholder_id entre os stakeholder_ids do requisito).
    - Linguagem simples, orientada ao valor; NÃO inclua técnica de explicabilidade, algoritmo ou tela.
    - O benefício ("para") deve decorrer do objetivo e da decisão apoiada da ficha; sem base, registre Lacuna.

    {{ _.role("user") }}
    REQUISITOS (fichas da Análise aprovada)
    {{ entrada.requisitos }}

    STAKEHOLDERS
    {{ entrada.stakeholders }}

    HISTÓRIAS EXISTENTES
    {{ entrada.historias_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 4.2.2 Define Acceptance Criteria — Dado/Quando/Então, em lotes de HU
// ---------------------------------------------------------------------------

class AcceptanceScenario {
  dado string @description("Contexto/pré-condição")
  quando string @description("Evento ou ação")
  entao string @description("Resultado observável e verificável")
}

class AcceptanceCriteria {
  id string? @description("CA-n existente; null se novo")
  hu_id string @description("HU-n a que os cenários se aplicam")
  cenarios AcceptanceScenario[]
  lacunas Lacuna[]
}

class AcceptanceCriteriaArtifact {
  criterios AcceptanceCriteria[]
}

class AcceptanceInput {
  historias UserStory[]
  requisitos SpecificationPlanEntry[]
  criterios_existentes AcceptanceCriteria[]
}

function DefineAcceptanceCriteria(entrada: AcceptanceInput, contexto: ContextItem[]) -> AcceptanceCriteriaArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 4.2.2 "Define Acceptance Criteria" do OpenUPExp: definir critérios de
    aceitação objetivos para cada História de Usuário de explicabilidade.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente um conjunto de critérios por HU da entrada (hu_id = HU-n), com um ou mais cenários
      no formato Dado / Quando / Então.
    - O "Então" descreve comportamento observável e verificável; evite termos vagos ("adequado",
      "rápido", "fácil", "claro") sem condição mensurável.
    - Critérios independentes de tecnologia, coerentes com o objetivo e as restrições da ficha.
    - Valores mensuráveis (tempos, quantidades) só se estiverem nas entradas; senão, registre Lacuna
      com a pergunta para os stakeholders.
    - Mantenha o id dos critérios existentes da mesma HU.

    {{ _.role("user") }}
    HISTÓRIAS DE USUÁRIO
    {{ entrada.historias }}

    FICHAS DOS REQUISITOS
    {{ entrada.requisitos }}

    CRITÉRIOS EXISTENTES
    {{ entrada.criterios_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 4.2.3 Specify Explanation Characteristics — em lotes de HU
// ---------------------------------------------------------------------------

class ExplanationCharacteristics {
  id string? @description("CEX-n existente; null se novo")
  hu_id string
  objetivo string? @description("Objetivo da explicação")
  publico_alvo string[] @description("STK-n que recebem a explicação")
  contexto_utilizacao string?
  nivel_detalhamento ExplanationDetailLevel?
  formato ExplanationFormat?
  momento ExplanationMoment?
  requisitos_qualidade string[] @description("Requisitos de qualidade da explicação presentes nas entradas")
  lacunas Lacuna[]
}

class ExplanationCharacteristicsArtifact {
  caracteristicas ExplanationCharacteristics[]
}

class CharacteristicsInput {
  historias UserStory[]
  requisitos SpecificationPlanEntry[]
  criterios AcceptanceCriteria[]
  limites_visao LimitAnswer[] @description("Respostas do checklist de limites da Visão (forma, momento, etc.)")
  caracteristicas_existentes ExplanationCharacteristics[]
}

function SpecifyExplanationCharacteristics(entrada: CharacteristicsInput, contexto: ContextItem[]) -> ExplanationCharacteristicsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 4.2.3 "Specify Explanation Characteristics" do OpenUPExp: descrever as
    características esperadas da explicação associada a cada História de Usuário.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente um registro por HU da entrada (hu_id = HU-n).
    - Características: objetivo, público-alvo, contexto de utilização, nível de detalhamento,
      formato de apresentação, momento em que a explicação é disponibilizada e requisitos de qualidade.
    - Use as respostas do checklist de limites da Visão quando tratarem de forma ou momento.
    - NÃO especifique algoritmos, técnicas de explicabilidade ou componentes de interface.
    - Campo sem evidência fica null e gera Lacuna com pergunta sugerida.

    {{ _.role("user") }}
    HISTÓRIAS DE USUÁRIO
    {{ entrada.historias }}

    FICHAS DOS REQUISITOS
    {{ entrada.requisitos }}

    CRITÉRIOS DE ACEITAÇÃO
    {{ entrada.criterios }}

    LIMITES DA EXPLICABILIDADE (Visão)
    {{ entrada.limites_visao }}

    CARACTERÍSTICAS EXISTENTES
    {{ entrada.caracteristicas_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 4.2.4 Establish Traceability — determinística (sem LLM); classe só para o schema
// ---------------------------------------------------------------------------

class TraceabilityRow {
  id string?
  hu string
  req string
  rer string?
  stakeholder string
  necessidades string[]
  origens string[] @description("RI-n/RC-n da Fase 2 consolidados no requisito")
  ca string?
  cex string?
  prioridade string?
}

class TraceabilityMatrix {
  linhas TraceabilityRow[]
}
