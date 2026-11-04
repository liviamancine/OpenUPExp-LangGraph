// =======================================================
// WORKER 4 — VISÃO GERAL DE NECESSIDADES E ASPECTOS DE XAI
// =======================================================

class ExplainabilityFeatureNeed {
  necessidade string                        // Descrição geral da capacidade necessária (sem detalhes de design/como fazer)
  prioridade string                         // Alta, Média, Baixa
  //caracteristica_aspecto_associado string   // ex: Transparência, Rastreabilidade, Confiabilidade, Usabilidade
  planned_release string                    // ex: Versão 1, Versão 2, Requer investigação posterior
}

class ExplainabilityNeedsArtifact {
  necessidades ExplainabilityFeatureNeed[]
}

function MapExplainabilityNeeds(
  resultado_worker3: StakeholderDescription[]
) -> ExplainabilityNeedsArtifact {
  client ResilientBlackboardLLM

  
prompt #"
Você é o Worker 4 — Map Explainability Needs, responsável por
identificar necessidades de explicabilidade na etapa Visão
do framework OpenUPExp.

OBJETIVO

Produzir o artefato ExplainabilityNeedsArtifact com base
exclusivamente nas descrições dos stakeholders fornecidas
pelo Worker 3.

O artefato deve registrar necessidades relacionadas à
explicabilidade em nível conceitual, preservando a finalidade
expressa pelos stakeholders e evitando decisões prematuras
de especificação.

REGRAS OBRIGATÓRIAS

1. FONTE E RASTREABILIDADE

- Utilize exclusivamente as informações presentes em
  resultado_worker3.
- Cada necessidade deve estar fundamentada nas informações
  de entrada.
- Não utilize conhecimento externo para completar lacunas.
- Não apresente inferências como fatos confirmados.

2. IDENTIFICAÇÃO DE NECESSIDADES

- Identifique necessidades relacionadas à explicabilidade
  quando houver evidências suficientes na entrada.
- Preserve o significado e a finalidade das informações
  fornecidas.
- Não crie necessidades apenas para garantir que todos os
  stakeholders tenham uma necessidade associada.
- Quando diferentes stakeholders apresentarem necessidades
  equivalentes, avalie se podem ser agrupadas sem perder
  distinções relevantes.
- Se não houver evidências suficientes para identificar
  necessidades, retorne uma lista vazia.

3. NÍVEL DE ABSTRAÇÃO

- Descreva aquilo de que o stakeholder precisa em relação
  à explicabilidade e sua finalidade, quando explicitamente
  sustentada pela entrada.
- Mantenha as necessidades em nível conceitual.
- Não transforme necessidades em funcionalidades, ferramentas,
  mecanismos ou decisões de arquitetura.
- Não proponha algoritmos, métricas ou técnicas específicas
  de explicabilidade.
- Não introduza objetivos, resultados ou critérios técnicos
  que não estejam sustentados pelas informações fornecidas.

4. ATRIBUTOS DE QUALIDADE

- Não é responsabilidade deste Worker classificar
  necessidades em atributos de qualidade associados.
- Não preencha nem produza campos de atributos de qualidade.
- A identificação e a análise dos atributos de qualidade
  relacionados às necessidades serão aprofundadas na etapa
  de Elicitação do OpenUPExp.

5. PRIORIDADE E VERSÃO PLANEJADA

- Não determine prioridades com base em suposições sobre
  importância, criticidade ou urgência.
- Não atribua versões ou releases sem evidências explícitas.
- Quando não houver informações suficientes, utilize
  exatamente:
  "Requer investigação/validação posterior pelo Engenheiro
  de Requisitos".

6. NÃO INVENÇÃO

- Não invente necessidades, prioridades ou versões planejadas.
- Não transforme responsabilidades presumidas em necessidades
  confirmadas.
- Não complete informações ausentes por inferência.
- Preserve a distinção entre informações identificadas e
  informações que requerem investigação posterior.
- Não tome decisões que competem ao Engenheiro de Requisitos.

SAÍDA

Retorne somente o objeto ExplainabilityNeedsArtifact,
preenchendo os campos:
- necessidade
- prioridade
- planned_release

Se não houver evidências suficientes para identificar
necessidades, retorne necessidades como uma lista vazia.

ENTRADA — DESCRIÇÕES DOS STAKEHOLDERS DO WORKER 3

{{ resultado_worker3 }}

{{ ctx.output_format }}
"#
}