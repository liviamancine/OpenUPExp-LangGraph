// Textos de ajuda (dicas ⓘ) das partes e dos campos, tirados do processo OpenUPExp
// (repositório liviamancine/OpenUPExp: artefatos/visao-explicabilidade.md e tarefas/definir-visao.md).

export type Help = { texto: string; fonte?: string };

export const PART_HELP: Record<string, Help> = {
  "vision.problem": {
    texto: "Visão geral do requisito de explicabilidade: por que e em qual contexto o sistema precisa explicar "
      + "suas decisões, os impactos e os critérios de sucesso.",
    fonte: "Documento de Visão, seção 1",
  },
  "vision.problem_statement": {
    texto: "Resume o problema que o projeto visa resolver: o problema da falta de explicabilidade, quem ele "
      + "afeta, qual o impacto e como seria uma solução bem-sucedida.",
    fonte: "Documento de Visão, seção 2.1",
  },
  "vision.positioning": {
    texto: "Uma declaração para cada perfil de usuário que necessita de explicabilidade. Comunica a intenção do "
      + "produto e sua importância para todos os envolvidos no projeto.",
    fonte: "Documento de Visão, seção 2.2",
  },
  "vision.stakeholders": {
    texto: "Os stakeholders que necessitam compreender, auditar ou validar as decisões do modelo, detalhando os "
      + "perfis da Declaração de Posicionamento: breve descrição e responsabilidades.",
    fonte: "Documento de Visão, seções 3.1 e 3.2",
  },
  "vision.stakeholder_needs": {
    texto: "O que cada stakeholder solicitou na elicitação focada em explicabilidade, nas palavras da fonte. "
      + "Sustenta as necessidades de explicabilidade.",
    fonte: "Definir a Visão, passo 4",
  },
  "vision.explainability_needs": {
    texto: "As capacidades necessárias e o porquê (não o como), em nível geral, com a prioridade e o lançamento "
      + "planejado. Os aspectos de explicabilidade são tratados na elicitação e na análise.",
    fonte: "Documento de Visão, seção 4.1",
  },
  "vision.complementary_requirements": {
    texto: "Informações complementares para o engenheiro conhecer o negócio antes das entrevistas: normas e "
      + "regulamentos, plataforma e desempenho, qualidade das explicações, restrições e documentação, sempre com a "
      + "fonte. Não são requisitos do sistema.",
    fonte: "Documento de Visão, seção 5",
  },
  "vision.limits": {
    texto: "Até onde a explicabilidade deve chegar: quais decisões exigem explicação, para quais stakeholders, que "
      + "tipos de explicação e em quais pontos de interação.",
    fonte: "Definir a Visão, passo 6",
  },
  "elicitation.plan": {
    texto: "Como conversar com cada stakeholder: o que se quer compreender, as técnicas, as perguntas e as dúvidas "
      + "da Visão que a conversa deve esclarecer.",
    fonte: "Encontrar e descrever requisitos, passo 1",
  },
  "elicitation.needs": {
    texto: "O que cada stakeholder pediu nas conversas (entrevistas, questionários, workshops), com as citações que "
      + "sustentam o pedido e a necessidade da Visão que ele aprofunda.",
    fonte: "Encontrar e descrever requisitos, passo 3",
  },
  glossary: {
    texto: "Vocabulário comum: termos do domínio e da explicabilidade com suas definições, para evitar "
      + "interpretações divergentes ao longo do projeto.",
    fonte: "Definir a Visão, passo 3",
  },
};

// Dica do código de cada item, pelo prefixo (RN-01, STK-01...).
export const ID_HELP: Record<string, string> = {
  STK: "Stakeholder: quem precisa compreender, auditar ou validar as decisões do sistema.",
  SN: "Solicitação: o que um stakeholder pediu, registrado na Visão.",
  NEED: "Necessidade de explicabilidade da Visão (seção 4.1).",
  POS: "Declaração de posicionamento de um perfil de usuário (Visão, seção 2.2).",
  CR: "Informação complementar da Visão (seção 5).",
  EP: "Item do plano de elicitação: a conversa planejada com um stakeholder.",
  RN: "Necessidade levantada: o que um stakeholder pediu nas conversas (entrevistas, questionários…). "
    + "É ligada a quem pediu, às citações e à necessidade da Visão que ela aprofunda.",
  RI: "Requisito de explicabilidade identificado a partir das necessidades levantadas.",
  RC: "Requisito complementar levantado na elicitação.",
  REQ: "Requisito consolidado: a versão final, que entra no Documento de Requisitos de Explicabilidade.",
};

// Dicas de campos que mudam conforme a parte (ver PART_FIELD_LABEL em components/ui.tsx).
export const PART_FIELD_HELP: Record<string, Record<string, string>> = {
  "elicitation.plan": {
    lacunas_alvo: "Pontos que ficaram sem resposta na Visão (os avisos \"Falta informação\") e que esta conversa deve esclarecer.",
    tecnicas: "Como a conversa será feita: entrevista, workshop, observação, análise de documentos ou protótipo.",
  },
  "elicitation.needs": {
    stakeholder_id: "Quem expressou a necessidade.",
    necessidade: "O que a pessoa precisa, resumido a partir do que ela disse.",
    decisao_alvo: "Qual decisão, recomendação ou previsão do sistema precisa ser explicada.",
    objetivo: "Para que serve a explicação. É uma classificação feita pela IA ao ler a conversa, numa lista fechada "
      + "tirada do passo 3 de \"Encontrar e descrever requisitos\": compreensão, justificativa, transparência, "
      + "rastreabilidade, auditoria, conformidade regulatória, confiança ou outro.",
    need_ids: "A necessidade da Visão (seção 4.1) que esta necessidade levantada aprofunda. Vazio quando a "
      + "necessidade é nova, surgida só nas conversas.",
  },
  "vision.complementary_requirements": {
    requisito: "Orientação para conhecer o negócio antes das entrevistas, por exemplo \"Importante disponibilizar "
      + "informações sobre ...\". Não é requisito do sistema.",
    justificativa: "Por que é importante conhecer esta informação antes das entrevistas e com quais necessidades ela se relaciona.",
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
  posicionamento_id: "O perfil da Declaração de Posicionamento (seção 2.2) que este stakeholder detalha.",
  // Declaração do Problema (seção 2.1)
  o_problema_da: "O problema que o projeto visa resolver, por exemplo a falta de explicabilidade das decisões.",
  afeta: "Os stakeholders impactados pelo problema.",
  cujo_impacto_e: "As consequências do problema: falta de confiança, barreiras legais, dificuldade de adoção ou de validação.",
  solucao_bem_sucedida: "Os benefícios esperados de uma solução: transparência, auditoria, aceitação do sistema.",
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
