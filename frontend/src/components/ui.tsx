import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const LABELS: Record<string, string> = {
  completed: "concluída", running: "executando", queued: "na fila", waiting_human: "aguardando humano",
  failed: "falhou", draft: "rascunho", in_review: "em revisão", approved: "aprovada", superseded: "substituída",
  stale: "desatualizada", verified: "citação verificada", unverified_quote: "citação não verificada",
  source_not_provided: "fonte não fornecida", open: "aberta", decided: "decidida", human_edit: "edição humana",
  agent: "agente", deterministic: "determinística", consolidation: "consolidação",
  concordo: "concordo", ressalvas: "concordo com ressalvas", objecao: "objeção",
  approval: "aprovação", consensus: "consenso", input: "entrada de material",
};

export const PHASE_NAMES: Record<string, string> = { "1": "Visão", "2": "Elicitação" };

export const DECISION_LABEL: Record<string, string> = {
  approve: "Aprovar",
  revisit_1_1: "Revisitar 1.1 Prepare Explainability Vision",
  revisit_1_2: "Revisitar 1.2 Develop Explainability Vision",
  revisit_2_1: "Revisitar 2.1 Prepare Explainability Elicitation",
  revisit_2_2: "Revisitar 2.2 Elicit Explainability Requirements",
  submit: "Material enviado: prosseguir com a extração",
  no_material: "Prosseguir sem material de elicitação (justifique)",
  close: "Encerrar o consenso",
};

export function Status({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{LABELS[value] ?? value}</span>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert err">{error instanceof Error ? error.message : String(error)}</div>;
}

export function Loading({ what = "Carregando" }: { what?: string }) {
  return <div className="muted">{what}…</div>;
}

export function Markdown({ children }: { children: string }) {
  return <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown></div>;
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode }[];
}) {
  return (
    <div className="tabs">
      {items.map((it) => (
        <button key={it.id} className={value === it.id ? "active" : ""} onClick={() => onChange(it.id)}>{it.label}</button>
      ))}
    </div>
  );
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(show).join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
