// Subprocesso 1.1 Prepare Explainability Vision
// Contratos derivados dos workers W1/W3 originais (legado), estendidos com IDs,
// origem e lacunas estruturadas.

// ---------------------------------------------------------------------------
// 1.1.1 Define Explainability Problem  (evolução do W1 AnalyzeExplainabilityScope)
// ---------------------------------------------------------------------------

class ProblemStatement {
  o_problema_da string @description("Template §2.1 — 'O problema da'")
  afeta string[] @description("Template §2.1 — 'afeta' (nomes literais da entrada)")
  cujo_impacto_e string[] @description("Template §2.1 — 'cujo o impacto é'")
  solucao_bem_sucedida string? @description("Template §2.1 — 'uma solução bem sucedida seria'")
}

class ExplainabilityProblem {
  necessidade_de_explicabilidade string
  descricao_geral string
  dominio_do_problema string
  stakeholders_mencionados string[] @description("Nomes literais de stakeholders citados na entrada")
  impactos string[]
  criterios_de_sucesso string?
  declaracao_problema ProblemStatement
  lacunas Lacuna[]
}

class DefineProblemInput {
  documento_escopo string
}

function DefineExplainabilityProblem(entrada: DefineProblemInput, contexto: ContextItem[]) -> ExplainabilityProblem {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você é um especialista em Engenharia de Requisitos para sistemas de IA, executando a tarefa
    1.1.1 "Define Explainability Problem" do processo OpenUPExp (Visão da Explicabilidade).

    OBJETIVO
    Identificar por que e em qual contexto o sistema inteligente precisa fornecer explicações
    sobre suas decisões ou comportamentos, e redigir a Declaração do Problema.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Descreva a necessidade de transparência sem presumir técnicas de XAI.
    - 'impactos': lista vazia se não houver impactos descritos.
    - 'declaracao_problema': preencha somente com o que a entrada sustenta.

    {{ _.role("user") }}
    DOCUMENTO DE ESCOPO DO PROJETO
    {{ entrada.documento_escopo }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 1.1.2 Identify Stakeholders  (absorve o W3 DescribeStakeholders)
// ---------------------------------------------------------------------------

class Stakeholder {
  id string? @description("STK-n de um stakeholder existente; null se for novo")
  nome string
  descricao string
  responsabilidade string? @description("Somente responsabilidade explicitamente sustentada pela entrada")
  ambiente_usuario string? @description("Template §3.2 — contexto de uso, plataformas, restrições, se houver evidência")
  origem OrigemRef[]
  lacunas Lacuna[]
}

class StakeholdersArtifact {
  stakeholders Stakeholder[]
}

class IdentifyStakeholdersInput {
  problema ExplainabilityProblem
  documento_escopo string
  stakeholders_existentes Stakeholder[]
}

function IdentifyStakeholders(entrada: IdentifyStakeholdersInput, contexto: ContextItem[]) -> StakeholdersArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.1.2 "Identify Stakeholders" do OpenUPExp: identificar quem precisa
    compreender, auditar, validar ou contestar as decisões do sistema de IA.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("STK") }}

    REGRAS ESPECÍFICAS
    - Considere os stakeholders mencionados no problema e no escopo. Não agrupe nem substitua.
    - 'descricao': relação do stakeholder com o sistema e com a explicabilidade, conforme a entrada.
    - 'responsabilidade': benefícios desejados ou objetivos do produto NÃO são responsabilidades.
      Sem evidência, deixe null e registre uma Lacuna.
    - 'origem': indique de onde veio cada stakeholder ('escopo' ou o campo do problema).

    {{ _.role("user") }}
    PROBLEMA DE EXPLICABILIDADE (1.1.1)
    {{ entrada.problema }}

    DOCUMENTO DE ESCOPO
    {{ entrada.documento_escopo }}

    STAKEHOLDERS EXISTENTES (preserve os IDs)
    {{ entrada.stakeholders_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 1.1.3 Identify Stakeholder Needs  — interpretação de trabalho (A-04):
// solicitações brutas, nas palavras da fonte, com origem rastreável.
// ---------------------------------------------------------------------------

class StakeholderNeed {
  id string? @description("SN-n existente; null se nova")
  stakeholder_id string @description("ID STK-n do stakeholder")
  solicitacao string @description("Nas palavras da fonte, sem reinterpretação")
  origem OrigemRef[]
}

class StakeholderNeedsArtifact {
  solicitacoes StakeholderNeed[]
}

class IdentifyStakeholderNeedsInput {
  stakeholders Stakeholder[]
  documento_escopo string
  solicitacoes_existentes StakeholderNeed[]
}

function IdentifyStakeholderNeeds(entrada: IdentifyStakeholderNeedsInput, contexto: ContextItem[]) -> StakeholderNeedsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.1.3 "Identify Stakeholder Needs" do OpenUPExp: registrar as
    solicitações de cada stakeholder relacionadas à compreensão das decisões do sistema,
    nas palavras da fonte, sem transformá-las ainda em requisitos ou necessidades conceituais.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("SN") }}

    REGRAS ESPECÍFICAS
    - Use o ID STK-n exato de cada stakeholder em 'stakeholder_id'.
    - Não crie solicitações só para que todo stakeholder tenha uma.
    - 'origem' deve apontar o trecho ou campo de onde a solicitação foi extraída.

    {{ _.role("user") }}
    STAKEHOLDERS
    {{ entrada.stakeholders }}

    DOCUMENTO DE ESCOPO
    {{ entrada.documento_escopo }}

    SOLICITAÇÕES EXISTENTES (preserve os IDs)
    {{ entrada.solicitacoes_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 1.1.4 Capture Domain Terminology / 1.1.5 Create Initial Glossary
// ---------------------------------------------------------------------------

class DomainTerm {
  id string? @description("DT-n existente; null se novo")
  termo string
  contexto_de_uso string @description("Frase ou trecho da entrada em que o termo aparece")
}

class DomainTermsArtifact {
  termos DomainTerm[]
}

class CaptureTermsInput {
  documento_escopo string
  problema ExplainabilityProblem
}

function CaptureDomainTerminology(entrada: CaptureTermsInput, contexto: ContextItem[]) -> DomainTermsArtifact {
  client OpenUPExpCheap
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.1.4 "Capture Domain Terminology" do OpenUPExp: capturar termos do
    domínio e de explicabilidade que precisam de entendimento comum entre stakeholders e equipe.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("DT") }}

    REGRAS ESPECÍFICAS
    - Capture apenas termos que aparecem nas entradas; 'contexto_de_uso' deve ser literal.
    - Priorize termos técnicos, siglas, papéis e conceitos com risco de ambiguidade.

    {{ _.role("user") }}
    DOCUMENTO DE ESCOPO
    {{ entrada.documento_escopo }}

    PROBLEMA DE EXPLICABILIDADE
    {{ entrada.problema }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

class GlossaryTerm {
  id string? @description("TERM-n existente; null se novo")
  termo string
  definicao string? @description("Definição sustentada pela entrada; null se a entrada não define")
  sinonimos string[]
  termo_origem_id string? @description("ID DT-n do termo capturado")
  lacunas Lacuna[]
}

class GlossaryArtifact {
  termos GlossaryTerm[]
}

class CreateGlossaryInput {
  termos DomainTerm[]
  glossario_existente GlossaryTerm[]
}

function CreateInitialGlossary(entrada: CreateGlossaryInput, contexto: ContextItem[]) -> GlossaryArtifact {
  client OpenUPExpCheap
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 1.1.5 "Create Initial Glossary" do OpenUPExp.

    {{ RegrasNaoInvencao() }}
    {{ RegrasIds("TERM") }}

    REGRAS ESPECÍFICAS
    - Uma entrada de glossário por termo capturado relevante; consolide sinônimos.
    - 'definicao' apenas quando o contexto de uso a sustenta; caso contrário null + Lacuna
      com uma pergunta sugerida para os stakeholders.

    {{ _.role("user") }}
    TERMOS CAPTURADOS (1.1.4)
    {{ entrada.termos }}

    GLOSSÁRIO EXISTENTE (preserve os IDs)
    {{ entrada.glossario_existente }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}
