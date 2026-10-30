import type { ReactNode } from "react";
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
  "1.1": "a preparação (leitura do escopo e das pessoas envolvidas)",
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
  stakeholder_id: "pessoa envolvida", stakeholder_ids: "pessoas envolvidas", need_ids: "necessidades",
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
  descricao: "descrição", prioridade: "prioridade", aspecto_associado: "aspecto associado", planned_release: "planned release",
};

export function fieldLabel(k: string): string {
  return FIELD_LABEL[k] ?? k.replace(/_/g, " ");
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
