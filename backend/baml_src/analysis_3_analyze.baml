// Fase 3 — Analyze Explainability Requirements
// Taxonomias e matriz de viabilidade: OpenUPExp/tarefas/analisar-requisito.md (passos 1–7).
// O template de Requisitos de Explicabilidade Refinados (RER) está marcado "???Validar" na
// teoria; os campos abaixo seguem as "perguntas úteis" do passo 1 (provisório, A-14/A-15).

// ---------------------------------------------------------------------------
// Taxonomias do passo 2, passo 3 e passo 6 (A-15: fechadas, com OUTRO justificado)
// ---------------------------------------------------------------------------

enum ExplanatoryAspect {
  COMPREENSAO @description("entender resultado")
  JUSTIFICATIVA @description("justificar decisão")
  CONFIANCA @description("aumentar aceitação")
  AUDITORIA @description("verificar comportamento")
  CONTESTACAO @description("questionar decisão")
  APRENDIZADO @description("ensinar funcionamento")
  OUTRO @description("Outro aspecto; justifique")
}

enum ExplanationType {
  FEATURE_IMPORTANCE @description("Importância dos atributos")
  LOCAL @description("Explicar caso específico")
  GLOBAL @description("Explicar comportamento geral")
  EXAMPLE_BASED @description("Demonstrar exemplos semelhantes")
  RULE_BASED @description("Mostrar regras")
  COUNTERFACTUAL @description("Mostrar impacto dos atributos (e se...?)")
  OUTRO @description("Outro tipo; justifique")
}

enum DecisionRisk {
  ALTO
  MEDIO
  BAIXO
}

enum ConflictKind {
  ENTRE_STAKEHOLDERS @description("Ex.: usuários querem explicações simples; auditores, alto detalhamento")
  TRANSPARENCIA_PRIVACIDADE @description("Transparência × privacidade")
  DETALHAMENTO_DESEMPENHO @description("Explicações mais detalhadas × desempenho")
  OUTRO
}

enum ConstraintKind {
  REGULATORIA
  ETICA
  TECNICA
  ORGANIZACIONAL
  OUTRA
}

enum FeasibilityCriterion {
  TECNICA
  REGULATORIA
  OPERACIONAL
  ECONOMICA
}

enum FeasibilityStatus {
  SIM
  NAO
  NAO_AVALIADO @description("Sem informação suficiente nas entradas; registre Lacuna")
}

enum MoSCoW {
  MUST @description("Essencial para os objetivos mínimos de explicabilidade")
  SHOULD @description("Importante, mas a ausência não inviabiliza o sistema")
  COULD @description("Desejável; pode ser adiado")
  WONT @description("Reconhecido, fora do escopo da iteração ou versão atual")
}

class RequirementIndexEntry {
  id string
  enunciado string
}

// ---------------------------------------------------------------------------
// 3.1.2 Consolidate and Characterize Requirements — por requisito (map)
// ---------------------------------------------------------------------------

class CharacterizedRequirement {
  id string? @description("RER-n existente; null se novo")
  req_id string @description("REQ-n caracterizado")
  contexto_uso string? @description("Em qual contexto a explicação será utilizada")
  usuarios_explicacao string[] @description("STK-n que utilizarão a explicação")
  decisao_apoiada string? @description("Qual decisão está sendo apoiada pelo sistema")
  risco_decisao DecisionRisk? @description("Risco/impacto da decisão; null se as entradas não sustentarem")
  objetivo_principal string? @description("Objetivo principal da explicação")
  obrigacao_regulatoria bool? @description("Existe obrigação regulatória de explicar? null se não houver evidência")
  requisitos_regulatorios string[] @description("REQ-n complementares ou normas citadas nas entradas que se associam")
  lacunas Lacuna[]
}

class CharacterizedRequirementsArtifact {
  caracterizacoes CharacterizedRequirement[]
}

class CharacterizeInput {
  requisito ConsolidatedRequirement
  stakeholders Stakeholder[]
  necessidades ExplainabilityNeed[]
  requisitos_complementares ConsolidatedRequirement[]
  caracterizacao_existente CharacterizedRequirement?
}

function CharacterizeRequirement(entrada: CharacterizeInput, contexto: ContextItem[]) -> CharacterizedRequirement {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.1.2 "Consolidate and Characterize Requirements" do OpenUPExp para
    UM requisito de explicabilidade: compreender seu contexto de uso e seus objetivos.

    {{ RegrasNaoInvencao() }}

    PERGUNTAS A RESPONDER (somente com base nas entradas)
    - Quem utilizará a explicação?
    - Qual decisão está sendo apoiada?
    - Qual o risco associado à decisão?
    - Qual o objetivo principal da explicação?
    - Existe obrigação regulatória para explicar a decisão?

    REGRAS ESPECÍFICAS
    - req_id = o id do requisito da entrada.
    - Campos sem evidência ficam null e geram Lacuna com pergunta sugerida.
    - Mantenha o id da caracterização existente, se houver.

    {{ _.role("user") }}
    REQUISITO
    {{ entrada.requisito }}

    STAKEHOLDERS ENVOLVIDOS
    {{ entrada.stakeholders }}

    NECESSIDADES DA VISÃO RELACIONADAS
    {{ entrada.necessidades }}

    REQUISITOS COMPLEMENTARES (normas, restrições)
    {{ entrada.requisitos_complementares }}

    CARACTERIZAÇÃO EXISTENTE
    {{ entrada.caracterizacao_existente }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.1 Classify Explainability Aspects — em lotes de requisitos
// ---------------------------------------------------------------------------

class AspectClassification {
  id string? @description("ASP-n existente; null se novo")
  req_id string
  aspectos ExplanatoryAspect[] @description("Classificação múltipla permitida")
  predominante ExplanatoryAspect
  justificativa string
  lacunas Lacuna[]
}

class AspectsArtifact {
  classificacoes AspectClassification[]
}

class ClassifyAspectsInput {
  requisitos ConsolidatedRequirement[]
  caracterizacoes CharacterizedRequirement[]
  classificacoes_existentes AspectClassification[]
}

function ClassifyExplainabilityAspects(entrada: ClassifyAspectsInput, contexto: ContextItem[]) -> AspectsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.1 "Classify Explainability Aspects" do OpenUPExp: classificar cada
    requisito pelo aspecto explicativo predominante.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente uma classificação por requisito da entrada (req_id = REQ-n).
    - Pode haver mais de um aspecto; indique o predominante.
    - Não assuma que todos os stakeholders têm os mesmos objetivos.
    - Use OUTRO só com justificativa explícita.

    {{ _.role("user") }}
    REQUISITOS
    {{ entrada.requisitos }}

    CARACTERIZAÇÕES (3.1.2)
    {{ entrada.caracterizacoes }}

    CLASSIFICAÇÕES EXISTENTES
    {{ entrada.classificacoes_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.2 Associate Requirements with Explanation Types — em lotes, com a base de referência
// ---------------------------------------------------------------------------

class ExplanationTypeMapping {
  id string? @description("MAP-n existente; null se novo")
  req_id string
  tipos ExplanationType[]
  justificativa string @description("Por que esses tipos atendem ao perfil, ao contexto e ao objetivo")
  evidencias EvidenceRef[] @description("Opcional: trechos da base de referência que sustentam o mapeamento")
  lacunas Lacuna[]
}

class ExplanationTypesArtifact {
  mapeamentos ExplanationTypeMapping[]
}

class MapTypesInput {
  requisitos ConsolidatedRequirement[]
  caracterizacoes CharacterizedRequirement[]
  aspectos AspectClassification[]
  mapeamentos_existentes ExplanationTypeMapping[]
}

function AssociateExplanationTypes(entrada: MapTypesInput, contexto: ContextItem[]) -> ExplanationTypesArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.2 "Associate Requirements with Explanation Types" do OpenUPExp:
    associar cada requisito a um ou mais tipos de explicação com maior aderência ao perfil do
    stakeholder, ao contexto da decisão e ao objetivo da explicação.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente um mapeamento por requisito da entrada.
    - NÃO selecione ferramentas, bibliotecas ou algoritmos específicos: apenas o tipo de explicação.
    - Exceção à regra 1 de rigor: você pode usar os trechos recuperados da base de referência para
      fundamentar o tipo; cite-os em evidencias (chunk_ref exato, citação literal).
    - Registre a justificativa e as limitações conhecidas como Lacuna.

    {{ _.role("user") }}
    REQUISITOS
    {{ entrada.requisitos }}

    CARACTERIZAÇÕES
    {{ entrada.caracterizacoes }}

    ASPECTOS EXPLICATIVOS (3.2.1)
    {{ entrada.aspectos }}

    MAPEAMENTOS EXISTENTES
    {{ entrada.mapeamentos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.3 Analyze Conflicts — sobre pares candidatos (cobertura de pares registrada)
// ---------------------------------------------------------------------------

class RequirementPair {
  a string
  b string
  motivo string @description("Por que o par foi selecionado para verificação")
}

class RequirementConflict {
  id string? @description("CNF-n existente; null se novo")
  req_ids string[] @description("Dois ou mais REQ-n em conflito")
  tipo ConflictKind
  descricao string
  stakeholder_ids string[]
  alternativas_resolucao string[] @description("Alternativas propostas; a decisão é dos stakeholders")
}

class ConflictsArtifact {
  conflitos RequirementConflict[]
}

class ConflictsInput {
  requisitos ConsolidatedRequirement[]
  aspectos AspectClassification[]
  tipos ExplanationTypeMapping[]
  pares_candidatos RequirementPair[]
  conflitos_existentes RequirementConflict[]
}

function AnalyzeConflicts(entrada: ConflictsInput, contexto: ContextItem[]) -> ConflictsArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.3 "Analyze Conflicts" do OpenUPExp: identificar conflitos entre
    requisitos, stakeholders e objetivos de explicabilidade.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Avalie TODOS os pares candidatos; devolva apenas os que têm conflito real.
    - Exemplos de conflito: explicações simples × alto detalhamento; transparência × privacidade;
      detalhamento × desempenho.
    - Proponha alternativas de resolução sem decidir por elas.
    - Mantenha o id de conflitos existentes que continuam válidos.

    {{ _.role("user") }}
    REQUISITOS
    {{ entrada.requisitos }}

    ASPECTOS
    {{ entrada.aspectos }}

    TIPOS DE EXPLICAÇÃO
    {{ entrada.tipos }}

    PARES CANDIDATOS
    {{ entrada.pares_candidatos }}

    CONFLITOS EXISTENTES
    {{ entrada.conflitos_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.4 Analyze Dependencies and Constraints — em lotes, com a base de referência
// ---------------------------------------------------------------------------

class RequirementConstraint {
  tipo ConstraintKind
  descricao string
  evidencias EvidenceRef[] @description("Trechos da base de referência (ex.: lei) que impõem a restrição")
}

class DependencyAnalysis {
  id string? @description("DEP-n existente; null se novo")
  req_id string
  depende_de string[] @description("REQ-n dos quais este depende (use o índice)")
  restricoes RequirementConstraint[]
  impacto string? @description("Impacto das restrições sobre o requisito")
  lacunas Lacuna[]
}

class DependenciesArtifact {
  dependencias DependencyAnalysis[]
}

class DependenciesInput {
  requisitos ConsolidatedRequirement[]
  caracterizacoes CharacterizedRequirement[]
  indice RequirementIndexEntry[] @description("Todos os requisitos do projeto, para referência")
  dependencias_existentes DependencyAnalysis[]
}

function AnalyzeDependencies(entrada: DependenciesInput, contexto: ContextItem[]) -> DependenciesArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.4 "Analyze Dependencies and Constraints" do OpenUPExp: identificar
    de quais outros requisitos cada requisito depende e quais restrições (regulatórias, éticas,
    técnicas, organizacionais) o impactam.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente uma análise por requisito da entrada.
    - depende_de só com REQ-n do índice.
    - Restrições regulatórias precisam de evidência recuperada (chunk_ref exato, citação literal);
      sem evidência, registre Lacuna em vez de afirmar a restrição.
    - Exemplo de registro: "REQ-01 depende de rastreabilidade; impactado pela LGPD".

    {{ _.role("user") }}
    REQUISITOS
    {{ entrada.requisitos }}

    CARACTERIZAÇÕES
    {{ entrada.caracterizacoes }}

    ÍNDICE DE REQUISITOS
    {{ entrada.indice }}

    ANÁLISES EXISTENTES
    {{ entrada.dependencias_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.5 Assess Feasibility — em lotes; matriz do passo 6
// ---------------------------------------------------------------------------

class FeasibilityItem {
  criterio FeasibilityCriterion
  situacao FeasibilityStatus
  observacao string?
}

class FeasibilityAssessment {
  id string? @description("FEA-n existente; null se novo")
  req_id string
  criterios FeasibilityItem[] @description("Os quatro critérios: TECNICA, REGULATORIA, OPERACIONAL, ECONOMICA")
  riscos string[]
  premissas string[]
  lacunas Lacuna[]
}

class FeasibilityArtifact {
  avaliacoes FeasibilityAssessment[]
}

class FeasibilityInput {
  requisitos ConsolidatedRequirement[]
  caracterizacoes CharacterizedRequirement[]
  tipos ExplanationTypeMapping[]
  dependencias DependencyAnalysis[]
  conflitos RequirementConflict[]
  avaliacoes_existentes FeasibilityAssessment[]
}

function AssessFeasibility(entrada: FeasibilityInput, contexto: ContextItem[]) -> FeasibilityArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.5 "Assess Feasibility" do OpenUPExp: avaliar se cada requisito pode
    ser atendido considerando o sistema de IA, as restrições do projeto e o contexto de uso.

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente uma avaliação por requisito, com os quatro critérios (técnica, regulatória,
      operacional, econômica).
    - Use NAO_AVALIADO quando as entradas não permitirem concluir, com Lacuna. A avaliação final é
      dos papéis Arquiteto de Software e Especialista em IA.
    - Registre riscos e premissas que possam afetar a implementação.

    {{ _.role("user") }}
    REQUISITOS
    {{ entrada.requisitos }}

    CARACTERIZAÇÕES
    {{ entrada.caracterizacoes }}

    TIPOS DE EXPLICAÇÃO
    {{ entrada.tipos }}

    DEPENDÊNCIAS E RESTRIÇÕES
    {{ entrada.dependencias }}

    CONFLITOS
    {{ entrada.conflitos }}

    AVALIAÇÕES EXISTENTES
    {{ entrada.avaliacoes_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}

// ---------------------------------------------------------------------------
// 3.2.6 Prioritize Requirements (MoSCoW) — visão global compacta (reduce)
// ---------------------------------------------------------------------------

class RequirementAnalysisSummary {
  id string
  enunciado string
  tipo string
  aspecto_predominante string?
  risco_decisao string?
  viabilidade string @description("Resumo dos quatro critérios, ex.: TECNICA=SIM REGULATORIA=NAO_AVALIADO")
  conflitos string[] @description("CNF-n em que o requisito aparece")
  depende_de string[]
}

class PriorityAssignment {
  id string? @description("PRI-n existente; null se novo")
  req_id string
  prioridade MoSCoW
  justificativa string
}

class PrioritiesArtifact {
  prioridades PriorityAssignment[]
}

class PrioritizeInput {
  requisitos RequirementAnalysisSummary[]
  prioridades_existentes PriorityAssignment[]
}

function PrioritizeRequirements(entrada: PrioritizeInput, contexto: ContextItem[]) -> PrioritiesArtifact {
  client OpenUPExpDefault
  prompt #"
    {{ _.role("system") }}
    Você executa a tarefa 3.2.6 "Prioritize Requirements" do OpenUPExp: SUGERIR a prioridade MoSCoW
    de cada requisito. A decisão final é humana, no consenso (A-16).

    {{ RegrasNaoInvencao() }}

    REGRAS ESPECÍFICAS
    - Exatamente uma prioridade por requisito da entrada; nenhum pode ficar sem prioridade.
    - Priorize depois de considerar conflitos, dependências e viabilidade.
    - Justifique cada classificação; um requisito do qual outros dependem não deve ficar abaixo deles.
    - Busque equilíbrio entre necessidades dos stakeholders, riscos e capacidade de implementação.

    {{ _.role("user") }}
    REQUISITOS ANALISADOS (visão compacta)
    {{ entrada.requisitos }}

    PRIORIDADES EXISTENTES
    {{ entrada.prioridades_existentes }}

    {{ ContextoAdicional(contexto) }}

    {{ ctx.output_format }}
  "#
}
