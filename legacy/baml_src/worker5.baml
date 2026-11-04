
class ExplainabilityAdditionalRequirementsQuery {
  consulta string
}

function GenerateAdditionalRequirementsQuery(
  documento_escopo: string,
  documento_visao: string
) -> ExplainabilityAdditionalRequirementsQuery {
  client ResilientBlackboardLLM

  prompt #"
Você é o Worker 5 do OpenUPExp.

Gere uma consulta para recuperar conhecimentos relevantes à
elaboração da Seção 5 — Requisitos Adicionais relacionados
à Explicabilidade do Documento de Visão.

Considere o escopo do projeto e o Documento de Visão produzido
pelos Workers anteriores.

A consulta deve abranger, quando pertinente:
- normas, padrões e regulamentos aplicáveis;
- restrições de plataforma, infraestrutura e desempenho;
- critérios de qualidade das explicações;
- restrições de design, dependências e assunções;
- documentação e suporte necessários.

REGRAS:
- Formule uma consulta objetiva e adequada à recuperação RAG.
- Considere o domínio e as necessidades identificadas no projeto.
- Não invente normas, restrições ou requisitos.
- Não defina prioridades nem versões planejadas.
- Não transforme exemplos de valores em requisitos confirmados.

ESCOPO DO PROJETO:
{{ documento_escopo }}

DOCUMENTO DE VISÃO:
{{ documento_visao }}

{{ ctx.output_format }}
"#
}
