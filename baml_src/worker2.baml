// =======================================================
// WORKER 2 — POSICIONAMENTO DA EXPLICABILIDADE (OpenUPExp)
// =======================================================

class ExplainabilityPositioning {
  stakeholder string
  para_quem string
  para_que string
  nome_produto string
  categoria_produto string
  beneficio_chave string
  unlike string
  our_product string
}

class ExplainabilityPositioningArtifact {
  posicionamentos ExplainabilityPositioning[]
}

function GenerateExplainabilityPositioning(
  escopo_worker1: ExplainabilityScope,
  documento_bruto: string
) -> ExplainabilityPositioningArtifact {
  client ResilientBlackboardLLM

  prompt #"
Você é o Worker 2 (Posicionamento da Explicabilidade) do framework OpenUPExp.

Sua função é transformar a necessidade de explicabilidade identificada no escopo inicial em uma Declaração de Posicionamento por perfil de stakeholder, 
alinhada aos padrões de Engenharia de Requisitos.

ENTRADA DE DADOS:
- Escopo Produzido pelo Worker 1: {{ escopo_worker1 }}
- Conteúdo do Projeto Fornecido: {{ documento_bruto }}

DIRETRIZES DE EXECUÇÃO:
1. Cardinalidade: Produza exatamente um posicionamento para cada stakeholder listado em 'stakeholders_afetados' no resultado do Worker 1.
2. Fidelidade às Evidências: Utilize unicamente as informações diretamente sustentadas pelas entradas. 
3. Gestão de Lacunas: Caso uma informação específica para a composição do posicionamento (ex: alternativa atual/unlike, benefício chave) não esteja explícita na entrada, registre de forma neutra que o item foi identificado como lacuna para validação/complementação pelo Engenheiro de Requisitos.
4. Generalidade: Não presuma tecnologias de IA, arquiteturas específicas ou processos que não estejam documentados na entrada.

{{ ctx.output_format }}
"#
}