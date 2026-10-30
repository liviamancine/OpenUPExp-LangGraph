// Textos de ajuda (dicas ⓘ) das partes e dos campos, tirados do processo OpenUPExp
// (repositório liviamancine/OpenUPExp: artefatos/visao-explicabilidade.md e tarefas/definir-visao.md).

export type Help = { texto: string; fonte?: string };

export const PART_HELP: Record<string, Help> = {
  "vision.problem": {
    texto: "Visão geral do requisito de explicabilidade: o problema da falta de explicabilidade, quem ele afeta, "
      + "qual o impacto e como seria uma solução bem-sucedida.",
    fonte: "Documento de Visão, seções 1 e 2.1",
  },
  "vision.positioning": {
    texto: "Uma declaração para cada perfil de usuário que necessita de explicabilidade. Comunica a intenção do "
      + "produto e sua importância para todos os envolvidos no projeto.",
    fonte: "Documento de Visão, seção 2.2",
  },
  "vision.stakeholders": {
    texto: "Os stakeholders que necessitam compreender, auditar ou validar as decisões do modelo: breve descrição, "
      + "responsabilidades e o ambiente em que interagem com as explicações.",
    fonte: "Documento de Visão, seções 3.1 e 3.2",
  },
  "vision.stakeholder_needs": {
    texto: "O que cada stakeholder solicitou na elicitação focada em explicabilidade, nas palavras da fonte. "
      + "Sustenta as necessidades de explicabilidade.",
    fonte: "Definir a Visão, passo 4",
  },
  "vision.explainability_needs": {
    texto: "As capacidades necessárias e o porquê (não o como), em nível geral, com a prioridade, a característica "
      + "ou aspecto associado e o lançamento planejado.",
    fonte: "Documento de Visão, seção 4.1",
  },
  "vision.complementary_requirements": {
    texto: "Requisitos adicionais que não são funcionalidades: padrões, normas e regulamentos, plataforma e "
      + "desempenho, qualidade das explicações, restrições, dependências e documentação.",
    fonte: "Documento de Visão, seção 5",
  },
  "vision.limits": {
    texto: "Até onde a explicabilidade deve chegar: quais decisões exigem explicação, para quais stakeholders, que "
      + "tipos de explicação e em quais pontos de interação.",
    fonte: "Definir a Visão, passo 6",
  },
  glossary: {
    texto: "Vocabulário comum: termos do domínio e da explicabilidade com suas definições, para evitar "
      + "interpretações divergentes ao longo do projeto.",
    fonte: "Definir a Visão, passo 3",
  },
};

export const FIELD_HELP: Record<string, string> = {
  // Declaração de Posicionamento (seção 2.2)
  para_quem: "Público-alvo: o perfil de usuário que necessita de explicabilidade.",
  para_que: "Por que esse público precisa de explicação: compreender, auditar ou confiar nas decisões do sistema.",
  nome_produto: "O nome do sistema. É o mesmo em todas as declarações de posicionamento.",
  categoria_produto: "Que tipo de sistema ele é (\"O [nome do produto] é um(a) [categoria]\"). É a mesma em todas as declarações.",
  beneficio_chave: "O que o produto faz para esse público: seu benefício principal.",
  unlike: "A principal alternativa concorrente: o que esse público usa hoje ou poderia usar no lugar do sistema.",
  our_product: "O principal diferencial do produto em relação a essa alternativa.",
  need_ids: "As necessidades de explicabilidade (seção 4.1) que esta declaração atende.",
  // Stakeholders (seções 3.1 e 3.2)
  descricao: "Breve descrição e a relação com o sistema ou com a explicabilidade.",
  responsabilidade: "Principais responsabilidades, interesses ou expectativas em relação à explicabilidade.",
  ambiente_usuario: "Contexto de uso: plataformas, restrições (regulatórias, de tempo real, acessibilidade) e integrações.",
  // Necessidades (seção 4.1)
  prioridade: "A prioridade indicada pelos stakeholders.",
  aspecto_associado: "A característica de explicabilidade relacionada, por exemplo transparência ou rastreabilidade.",
  planned_release: "Em que versão a necessidade deve ser atendida.",
  stakeholder_ids: "Os stakeholders ligados a este item.",
  solicitacao_ids: "As solicitações dos stakeholders que sustentam esta necessidade.",
  // Requisitos adicionais (seção 5)
  justificativa: "A relação entre a necessidade da Visão e a evidência (lei, norma ou recomendação).",
};
