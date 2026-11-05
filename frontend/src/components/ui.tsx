import { createContext, useContext, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Icon, { type IconName } from "./Icon";

// Vocabulário da interface: termos simples; o termo do processo aparece só como complemento.
const LABELS: Record<string, string> = {
  completed: "concluída", running: "em andamento", queued: "na fila", waiting_human: "aguardando você",
  failed: "com erro", draft: "rascunho", in_review: "em revisão", approved: "aprovada", superseded: "substituída",
  stale: "desatualizada", verified: "citação conferida", unverified_quote: "citação não encontrada",
  source_not_provided: "sem fonte", open: "pendente", decided: "resolvida", human_edit: "editada por você",
  agent: "feita pela IA", deterministic: "automática", consolidation: "documento montado",
  concordo: "concorda", ressalvas: "concorda com observações", objecao: "discorda",
  approval: "aprovação", consensus: "opinião da equipe", input: "envio de material",
  ready: "pronta", building: "preparando",
};

export interface PhaseInfo { nome: string; titulo: string; descricao: string; icon: IconName }

export const PHASES: Record<string, PhaseInfo> = {
  "1": { nome: "Visão", titulo: "Entender o problema", icon: "eye",
    descricao: "A IA lê o escopo do projeto e propõe quem precisa de explicações sobre as decisões do sistema e por quê." },
  "2": { nome: "Elicitação", titulo: "Ouvir as pessoas", icon: "chat",
    descricao: "Você conversa com os envolvidos e envia o material. A IA extrai as necessidades e escreve os requisitos." },
  "3": { nome: "Análise", titulo: "Analisar e priorizar", icon: "search",
    descricao: "A IA procura conflitos, dependências e limitações, e sugere o que é mais importante." },
  "4": { nome: "Especificação", titulo: "Escrever a especificação", icon: "file",
    descricao: "A IA escreve histórias de usuário, critérios de aceitação e a ligação entre tudo." },
};

export const PHASE_NAMES: Record<string, string> = Object.fromEntries(Object.entries(PHASES).map(([k, v]) => [k, v.nome]));

export const SUBPROCESS_NAMES: Record<string, string> = {
  "1.1": "a preparação (leitura do escopo e dos stakeholders)",
  "1.2": "o desenvolvimento da visão (necessidades, posicionamento e limites)",
  "2.1": "o planejamento das conversas",
  "2.2": "o levantamento das necessidades e dos requisitos",
  "3.1": "a preparação da análise",
  "3.2": "a análise (conflitos, dependências, viabilidade e prioridades)",
  "4.1": "a preparação da especificação",
  "4.2": "a escrita das histórias, critérios e características",
};

const DECISIONS: Record<string, string> = {
  approve: "Aprovar e montar o documento final",
  submit: "Material enviado: pode continuar",
  no_material: "Continuar sem material (explique o motivo)",
  close: "Encerrar: a equipe está de acordo",
};

export function decisionLabel(key: string): string {
  const m = key.match(/^revisit_(\d)_(\d)$/);
  if (m) return `Pedir para a IA refazer ${SUBPROCESS_NAMES[`${m[1]}.${m[2]}`] ?? `${m[1]}.${m[2]}`}`;
  return DECISIONS[key] ?? key;
}

export function decisionHelp(key: string): string {
  if (key.startsWith("revisit_")) return "A IA refaz esta parte e tudo o que vem depois, usando o seu comentário como orientação.";
  return {
    approve: "Esta etapa fica aprovada e entra no documento final.",
    submit: "A IA vai ler o material enviado e extrair as necessidades de cada pessoa.",
    no_material: "A IA usa só o que já existe na Visão. Use quando não for possível conversar com as pessoas.",
    close: "Registra o acordo da equipe e segue para a revisão final.",
  }[key] ?? "";
}

export const MECHANISM: Record<string, { label: string; icon: IconName }> = {
  agent: { label: "IA", icon: "sparkles" },
  deterministic: { label: "Automático", icon: "zap" },
  hitl_approval: { label: "Você aprova", icon: "checkCircle" },
  hitl_consensus: { label: "Equipe opina", icon: "thumbsUp" },
};

export const ROLE_LABEL: Record<string, string> = {
  requirements_engineer: "Responsável pelos requisitos", participant: "Participante", observer: "Observador",
  researcher: "Pesquisador", admin: "Administrador",
};

// Nomes amigáveis para os campos dos resultados (o restante usa o nome do campo sem "_").
const FIELD_LABEL: Record<string, string> = {
  stakeholder_id: "stakeholder", stakeholder_ids: "stakeholders", need_ids: "necessidades",
  solicitacao_ids: "solicitações", req_id: "requisito", req_ids: "requisitos", hu_id: "história",
  rn_ids: "necessidades levantadas", origem_ids: "origem", ri_ids: "requisitos identificados",
  cr_ids: "requisitos complementares", depende_de: "depende de", usuarios_explicacao: "quem usa a explicação",
  publico_alvo: "público", decisao_apoiada: "decisão apoiada", risco_decisao: "risco da decisão",
  objetivo_principal: "objetivo", contexto_uso: "contexto de uso", contexto_utilizacao: "contexto de uso",
  nivel_detalhamento: "nível de detalhe", requisitos_qualidade: "qualidade esperada", cenarios: "cenários",
  entao: "então", justificativa_agrupamento: "por que foram agrupados", alternativas_resolucao: "como resolver",
  termo_origem_id: "termo de origem", para_quem: "para quem", para_que: "para que",
  // rótulos da Declaração de Posicionamento, como no Documento de Visão (seção 2.2)
  nome_produto: "nome do produto", categoria_produto: "categoria do produto", beneficio_chave: "que (benefício principal)",
  unlike: "unlike (principal alternativa)", our_product: "our product (diferencial)", ambiente_usuario: "ambiente do usuário",
  posicionamento_id: "perfil (posicionamento)", o_problema_da: "o problema da", afeta: "afeta",
  cujo_impacto_e: "cujo impacto é", solucao_bem_sucedida: "uma solução bem-sucedida seria",
  descricao: "descrição", prioridade: "prioridade", aspecto_associado: "aspecto associado", planned_release: "planned release",
  decisao_alvo: "decisão a ser explicada", lacunas_alvo: "dúvidas da Visão que esta conversa deve esclarecer",
  tecnicas: "técnicas", perguntas: "perguntas", enunciado: "enunciado", solicitacao: "solicitação",
  necessidade: "necessidade", responsabilidade: "responsabilidade", justificativa: "justificativa",
};

export function fieldLabel(k: string): string {
  return FIELD_LABEL[k] ?? k.replace(/_/g, " ");
}

// Rótulos que mudam conforme a parte do documento (ex.: nas Informações complementares da Visão,
// o campo "requisito" é uma informação, não um requisito).
const PART_FIELD_LABEL: Record<string, Record<string, string>> = {
  "vision.complementary_requirements": { requisito: "informação", justificativa: "por que importa",
    requisitos: "informações" },
  "elicitation.plan": { need_ids: "necessidades da Visão", objetivo: "o que se quer compreender" },
  "elicitation.needs": { objetivo: "objetivo da explicação", need_ids: "aprofunda a necessidade da Visão",
    necessidades: "necessidades levantadas" },
  "requirements.identified": { need_ids: "necessidades da Visão", rn_ids: "necessidades levantadas" },
  "requirements.consolidated": { need_ids: "necessidades da Visão", objetivo: "objetivo da explicação" },
};

// Nome de um item de lista que muda conforme a parte (botões Adicionar/Remover do formulário).
export const PART_ITEM_NOUN: Record<string, Record<string, string>> = {
  "vision.complementary_requirements": { requisitos: "informação" },
};

// Valores de listas fechadas com nome legível (o mesmo dicionário de backend/openupexp/domain/labels.py).
const VALUE_LABEL: Record<string, string> = {
  ENTREVISTA: "Entrevista", WORKSHOP: "Workshop", OBSERVACAO: "Observação", ANALISE_DOCUMENTAL: "Análise documental",
  PROTOTIPO: "Protótipo", OUTRA: "Outra",
  COMPREENSAO: "Compreensão", JUSTIFICATIVA: "Justificativa", TRANSPARENCIA: "Transparência",
  RASTREABILIDADE: "Rastreabilidade", AUDITORIA: "Auditoria", CONFORMIDADE_REGULATORIA: "Conformidade regulatória",
  CONFIANCA: "Confiança", OUTRO: "Outro", CONTESTACAO: "Contestação", APRENDIZADO: "Aprendizado",
  EXPLICABILIDADE: "Explicabilidade", COMPLEMENTAR: "Complementar",
  NORMAS_REGULAMENTOS: "Padrões, normas e regulamentos", PLATAFORMA_DESEMPENHO: "Plataforma, hardware e desempenho",
  QUALIDADE_EXPLICACOES: "Qualidade das explicações", RESTRICOES_DEPENDENCIAS: "Restrições, dependências e assunções",
  DOCUMENTACAO_SUPORTE: "Documentação e suporte",
  OBRIGACAO_NORMATIVA: "Exigência legal", RECOMENDACAO_TECNICA: "Recomendação técnica", DERIVADO_VISAO: "Vem da Visão",
  ALTO: "Alto", MEDIO: "Médio", BAIXO: "Baixo",
};

export function valueLabel(v: string): string {
  if (VALUE_LABEL[v]) return VALUE_LABEL[v];
  // outro valor de lista fechada (MAIUSCULAS_COM_SUBLINHADO): só a primeira letra maiúscula
  return /^[A-Z][A-Z_]+$/.test(v) ? (v.charAt(0) + v.slice(1).toLowerCase()).replace(/_/g, " ") : v;
}

/** ID -> nome dos itens da execução (e da Visão de base), para mostrar o nome ao lado do código. */
export const LabelsContext = createContext<Record<string, string>>({});
export const ITEM_ID = /^[A-Z]{2,4}-\d+$/;

function shortName(text: string, n = 70): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length <= n ? t : `${t.slice(0, n - 1).replace(/[ ,.;:]+$/, "")}…`;
}

/** "Solicitante MEI STK-01": o nome em destaque e o código pequeno ao lado. */
export function Ref({ id }: { id: string }) {
  const name = useContext(LabelsContext)[id];
  if (!name) return <span className="code-chip">{id}</span>;
  return <span className="ref" title={name.length > 70 ? name : undefined}>{shortName(name)} <span className="code-chip">{id}</span></span>;
}

/** Valor de um campo na leitura: códigos viram nome + código; listas fechadas, nome legível. */
export function FieldValue({ value }: { value: unknown }) {
  const names = useContext(LabelsContext);
  const one = (x: string, i: number, sep: string) => (
    <span key={i}>{i > 0 && sep}{ITEM_ID.test(x) ? <Ref id={x} /> : valueLabel(x)}</span>
  );
  if (typeof value === "string") return one(value, 0, "");
  if (Array.isArray(value) && value.length && value.every((x) => typeof x === "string")) {
    const list = value as string[];
    const ids = list.some((x) => ITEM_ID.test(x));
    // frases (perguntas, dúvidas) ficam uma por linha; nomes curtos, na mesma linha
    // códigos de itens com nomes longos (necessidades, requisitos): um por linha
    if (ids && list.length > 1 && list.some((x) => (names[x] ?? "").length > 30)) {
      return <ul className="plain-list">{list.map((x, i) => <li key={i}><Ref id={x} /></li>)}</ul>;
    }
    if (!ids && list.length > 1 && list.some((x) => x.length > 40)) {
      return <ul className="plain-list">{list.map((x, i) => <li key={i}>{valueLabel(x)}</li>)}</ul>;
    }
    return <>{list.map((x, i) => one(x, i, ids ? "; " : ", "))}</>;
  }
  return <>{show(value)}</>;
}

/** Tipo da parte aberta, para rótulos e dicas próprios dela. */
export const PartTypeContext = createContext<string>("");

export function usePartLabel(): (k: string) => string {
  const part = useContext(PartTypeContext);
  return (k) => PART_FIELD_LABEL[part]?.[k] ?? fieldLabel(k);
}

const STATUS_ICON: Record<string, IconName> = {
  completed: "checkCircle", approved: "checkCircle", running: "clock", queued: "clock", waiting_human: "bell",
  failed: "xCircle", stale: "alert", open: "bell", decided: "check",
};

export function Status({ value }: { value: string }) {
  const icon = STATUS_ICON[value];
  return <span className={`badge ${value}`}>{icon && <Icon name={icon} size={12} />}{LABELS[value] ?? value}</span>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert err"><Icon name="alert" /><div>{error instanceof Error ? error.message : String(error)}</div></div>;
}

export function Loading({ what = "Carregando" }: { what?: string }) {
  return <div className="loading"><span className="spinner" />{what}…</div>;
}

export function Markdown({ children }: { children: string }) {
  return <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown></div>;
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode; icon?: IconName }[];
}) {
  return (
    <div className="tabs" role="tablist">
      {items.map((it) => (
        <button key={it.id} type="button" role="tab" aria-selected={value === it.id}
          className={value === it.id ? "active" : ""} onClick={() => onChange(it.id)}>
          {it.icon && <Icon name={it.icon} size={16} />}{it.label}
        </button>
      ))}
    </div>
  );
}

export function PhaseIcon({ phase, size = 22 }: { phase: string; size?: number }) {
  return <span className={`phase-icon p${phase}`}><Icon name={PHASES[phase]?.icon ?? "layers"} size={size} /></span>;
}

export function PhaseChip({ phase }: { phase: string }) {
  const p = PHASES[phase];
  return (
    <span className={`phase-chip p${phase}`}>
      <Icon name={p?.icon ?? "layers"} size={13} />Etapa {phase}{p ? ` · ${p.titulo}` : ""}
    </span>
  );
}

export function Empty({ icon = "info", children }: { icon?: IconName; children: ReactNode }) {
  return <div className="empty"><Icon name={icon} size={28} /><div>{children}</div></div>;
}

/** Dica ⓘ: abre ao passar o mouse, ao focar com Tab ou ao tocar. */
export function InfoTip({ text, source }: { text?: string; source?: string }) {
  if (!text) return null;
  return (
    <span className="info-tip" tabIndex={0} role="button" aria-label={`Ajuda: ${text}`}
      onClick={(e) => { e.stopPropagation(); e.preventDefault(); }}>
      <Icon name="info" size={14} />
      <span className="tip" role="tooltip">{text}{source && <span className="tip-source">{source}</span>}</span>
    </span>
  );
}

export function Hint({ children, icon = "info", tone = "info" }: { children: ReactNode; icon?: IconName; tone?: string }) {
  return <div className={`alert ${tone}`}><Icon name={icon} /><div>{children}</div></div>;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(show).join(value.some((v) => typeof v === "object") ? " · " : ", ") : "—";
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([k, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length) && k !== "verificacao")
      .map(([k, v]) => `${fieldLabel(k)}: ${show(v)}`).join("; ");
  }
  return String(value);
}
