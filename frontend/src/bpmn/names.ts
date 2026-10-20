/**
 * Nomes em português para a interface. Os BPMN da teoria e o manifesto continuam em inglês;
 * a tradução é aplicada só na exibição (lista de tarefas e texto dos diagramas).
 */
import type { Manifest } from "../api/types";

const TASKS: Record<string, string> = {
  "1": "Definir a Visão da explicabilidade",
  "1.1": "Preparar a Visão",
  "1.1.1": "Definir o problema de explicabilidade",
  "1.1.2": "Identificar as pessoas envolvidas",
  "1.1.3": "Identificar as necessidades das pessoas envolvidas",
  "1.1.4": "Levantar os termos do domínio",
  "1.1.5": "Criar o glossário inicial",
  "1.2": "Desenvolver a Visão",
  "1.2.1": "Identificar as necessidades de explicabilidade",
  "1.2.pos": "Escrever o posicionamento da explicabilidade",
  "1.2.2": "Identificar requisitos complementares",
  "1.2.3": "Definir o escopo e os limites da explicabilidade",
  "1.2.4": "Montar o rascunho da Visão",
  "1.3": "Validar a Visão",
  "1.3.1": "Revisar a Visão",
  "1.3.gate": "A Visão está aprovada?",
  "1.3.2": "Consolidar a Visão",
  "2": "Levantar os requisitos de explicabilidade",
  "2.1": "Preparar as conversas",
  "2.1.1": "Revisar a Visão aprovada",
  "2.1.2": "Planejar as conversas",
  "2.2": "Levantar os requisitos",
  "2.2.1": "Obter as necessidades de explicabilidade",
  "2.2.1.in": "Enviar o material das conversas",
  "2.2.2": "Identificar os requisitos de explicabilidade",
  "2.2.3": "Identificar requisitos complementares",
  "2.2.4": "Organizar e consolidar os requisitos",
  "2.2.5": "Buscar o consenso da equipe",
  "2.3": "Validar os requisitos",
  "2.3.1": "Revisar os requisitos",
  "2.3.gate": "Os requisitos estão aprovados?",
  "2.3.2": "Consolidar os requisitos",
  "3": "Analisar os requisitos de explicabilidade",
  "3.1": "Preparar a análise",
  "3.1.1": "Revisar os requisitos aprovados",
  "3.1.2": "Consolidar e caracterizar os requisitos",
  "3.2": "Analisar os requisitos",
  "3.2.1": "Classificar os aspectos de explicabilidade",
  "3.2.2": "Associar os requisitos a tipos de explicação",
  "3.2.3": "Analisar conflitos",
  "3.2.4": "Analisar dependências e restrições",
  "3.2.5": "Avaliar a viabilidade",
  "3.2.6": "Priorizar os requisitos",
  "3.2.7": "Buscar o consenso da equipe",
  "3.3": "Validar a análise",
  "3.3.1": "Revisar os requisitos analisados",
  "3.3.gate": "A análise está aprovada?",
  "3.3.2": "Consolidar o documento de requisitos",
  "4": "Especificar a explicabilidade",
  "4.1": "Preparar a especificação",
  "4.1.1": "Revisar os requisitos analisados",
  "4.1.2": "Preparar as fichas de especificação",
  "4.2": "Especificar os requisitos",
  "4.2.1": "Escrever as histórias de usuário",
  "4.2.2": "Definir os critérios de aceitação",
  "4.2.3": "Especificar as características da explicação",
  "4.2.4": "Estabelecer a rastreabilidade",
  "4.2.5": "Buscar o consenso da equipe",
  "4.3": "Validar a especificação",
  "4.3.1": "Revisar a especificação",
  "4.3.gate": "A especificação está aprovada?",
  "4.3.2": "Consolidar o documento de requisitos",
};

/** Nome em português de uma tarefa, subprocesso ou fase (pelo id do manifesto). */
export function taskName(id: string, fallback?: string | null): string {
  return TASKS[id] ?? fallback ?? id;
}

// Demais textos dos diagramas (documentos, bases, raias, fluxos), pelo texto original normalizado.
const TEXTS: Record<string, string> = {
  "Acceptance Criteria": "Critérios de aceitação",
  "Analyzed Explainability Requirements": "Requisitos analisados",
  "Caracteristicas especificadas": "Características especificadas",
  "Characterized Explainability Requirements": "Requisitos caracterizados",
  "Conflicts and solutions identified": "Conflitos e soluções identificados",
  "Consolidated Explainability Requirements": "Requisitos consolidados",
  "Draf Explainability Vision": "Rascunho da Visão",
  "Draft Explainability Vision": "Rascunho da Visão",
  "ERD": "Documento de requisitos",
  "Explainability Elicitation Plan": "Plano das conversas",
  "Explainability Requirement Document (ERD)": "Documento de requisitos de explicabilidade",
  "Explainability Vision": "Visão da explicabilidade",
  "Feasibility assesses": "Avaliação de viabilidade",
  "Identified Complemenatary Requirements": "Requisitos complementares identificados",
  "Identified Requirements": "Requisitos identificados",
  "Impacts of assessed dependecies": "Impactos das dependências",
  "Initial Glossary": "Glossário inicial",
  "Mapping of explanation types": "Tipos de explicação associados",
  "MoSCoW Priorities": "Prioridades (MoSCoW)",
  "Project Scope Business Needs/objectives": "Escopo do projeto e objetivos de negócio",
  "Specified Explainability Requirements": "Requisitos especificados",
  "Stakeholde List, Stakeholder Needs, Initial Glossary": "Pessoas envolvidas, necessidades e glossário",
  "Stakeholder List, Stakeholder Needs, Initial Glossary": "Pessoas envolvidas, necessidades e glossário",
  "Stakeholders List": "Pessoas envolvidas",
  "Stakeholders Needs": "Necessidades das pessoas envolvidas",
  "Traceability Matrix": "Matriz de rastreabilidade",
  "User Stories": "Histórias de usuário",
  "Explainability Reference Base": "Base de consulta (leis, manuais, artigos)",
  "Requirements Engineer": "Engenheiro(a) de Requisitos",
  "Requirements Enginee": "Engenheiro(a) de Requisitos",
  "Yes": "Sim",
  "No": "Não",
  "Create Explainability Requirement Document (ERD)": "Criar o documento de requisitos de explicabilidade",
  "Explainability Elicitation Strategy": "Estratégia das conversas",
};

const norm = (s: string) => s.replace(/ /g, " ").replace(/\s+/g, " ").trim();

function translateText(text: string): string | null {
  const t = norm(text);
  if (TEXTS[t]) return TEXTS[t];
  const revisit = t.match(/decides whether to revisit subprocess (\d)\.1 or \d\.2/);
  if (revisit) {
    const p = revisit[1];
    return `Se não aprovar, escolha refazer ${p}.1 ou ${p}.2`;
  }
  return null;
}

/** Elemento BPMN → id do manifesto (fases, subprocessos e tarefas). */
function elementIds(manifest: Manifest): Map<string, string> {
  const map = new Map<string, string>();
  for (const ph of manifest.phases) {
    map.set(ph.bpmn_element, ph.id);
    for (const sp of ph.subprocesses) {
      map.set(sp.bpmn_element, sp.id);
      for (const t of sp.tasks) if (t.bpmn_element) map.set(t.bpmn_element, t.id);
    }
  }
  return map;
}

/** Traduz o XML de um diagrama antes de exibi-lo. Em caso de erro, devolve o original. */
export function translateBpmn(xml: string, manifest: Manifest): string {
  try {
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    if (doc.getElementsByTagName("parsererror").length) return xml;
    const ids = elementIds(manifest);
    for (const el of Array.from(doc.querySelectorAll("[name]"))) {
      if (el.localName === "Font" || el.namespaceURI?.includes("bizagi")) continue;
      const id = ids.get(el.getAttribute("id") ?? "");
      const name = el.getAttribute("name") ?? "";
      const pt = id ? `${id} ${taskName(id, name)}` : translateText(name);
      if (pt && name) el.setAttribute("name", id && /\.gate$/.test(id) ? taskName(id) : pt);
    }
    for (const el of Array.from(doc.getElementsByTagNameNS("*", "text"))) {
      const pt = translateText(el.textContent ?? "");
      if (pt) el.textContent = pt;
    }
    return new XMLSerializer().serializeToString(doc);
  } catch {
    return xml;
  }
}
