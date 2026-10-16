class ExplainabilityScope {
  necessidade_de_explicabilidade string
  stakeholders_afetados string[]
  impactos string[]
  criterios_de_sucesso string
  descricao_geral string
  dominio_do_problema string
}

class ExplainabilityScopeArtifact {
  escopo ExplainabilityScope
}

function AnalyzeExplainabilityScope(
  documento_escopo: string
) -> ExplainabilityScopeArtifact {
  //client GroqLlama
  // Alterado de GroqLlama para o cliente resiliente em Fallback
  client ResilientBlackboardLLM

prompt #"
Você é o Worker 1 da pipeline do OpenUPExp (Especialista em Engenharia de Requisitos para IA).
Atue na atividade 1.1.1 "Define Explainability Need" (Visão da Explicabilidade).

OBJETIVO
Analise o conteúdo e identifique por que e em qual contexto o sistema inteligente precisa fornecer explicações sobre suas decisões ou comportamentos.

REGRAS DE EXTRAÇÃO E RIGOR CIENTÍFICO (NÃO-INVENÇÃO)
1. Fonte Única: Baseie-se EXCLUSIVAMENTE nas informações fornecidas. Não use conhecimento externo nem faça inferências plausíveis.
2. Necessidade de Explicabilidade: Descreva o motivo da transparência sem presumir técnicas específicas de XAI (ex: SHAP, LIME, interfaces).
3. Stakeholders e Domínio: Preserve exatamente os nomes, termos e domínios mencionados na entrada.
4. Dados Ausentes: 
   - Para campos de texto (`criterios_de_sucesso`, etc.), se a informação não constar explicitamente, defina como: "Não identificado nas informações fornecidas na entrada; requer investigação posterior."
   - Para listas (`impactos`), se não houver impactos descritos, retorne uma lista vazia.

ENTRADA:
{{ documento_escopo }}

{{ ctx.output_format }}
"#
}

test explainability_scope_test {
  functions [AnalyzeExplainabilityScope]

  args {
    documento_escopo #"
     O projeto consiste no desenvolvimento de um sistema
      inteligente para analisar propostas de financiamento
      imobiliário.

      O sistema utilizará dados financeiros e informações
      cadastrais dos solicitantes para apoiar a análise
      das propostas de crédito.

      Os analistas precisam compreender os fatores
      considerados pelo sistema para avaliar e validar
     as recomendações.
     
    "#
  }
}



