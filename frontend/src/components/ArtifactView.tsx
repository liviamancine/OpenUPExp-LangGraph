import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Evidence, ItemComment, VersionDetail } from "../api/types";
import { SchemaForm } from "./SchemaForm";
import Icon from "./Icon";
import { ErrorBox, Loading, Markdown, Status, fieldLabel, show } from "./ui";

const LIST_FIELD: Record<string, string> = {
  "vision.stakeholders": "stakeholders", "vision.stakeholder_needs": "solicitacoes", "vision.domain_terms": "termos",
  glossary: "termos", "vision.explainability_needs": "necessidades", "vision.positioning": "posicionamentos",
  "vision.complementary_requirements": "requisitos", "vision.limits": "respostas", "vision.reference_queries": "consultas",
};
const HIDDEN = new Set(["id", "lacunas", "origem", "evidencias", "lacuna", "baseada_em", "descartados"]);

export default function ArtifactView({ versionId, onComment, onNewVersion }: {
  versionId: string; onComment?: (c: ItemComment) => void; onNewVersion?: (id: string) => void;
}) {
  const qc = useQueryClient();
  const v = useQuery({ queryKey: ["version", versionId], queryFn: () => api.get<VersionDetail>(`/artifact-versions/${versionId}`) });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<unknown>(null);
  const schema = useQuery({
    queryKey: ["schema", v.data?.artifact_type], enabled: editing && !!v.data,
    queryFn: () => api.get<Record<string, unknown>>(`/artifact-types/${v.data!.artifact_type}/schema`),
  });
  const save = useMutation({
    mutationFn: () => api.post<{ id: string }>(`/artifact-versions/${versionId}/edits`, { content: draft }),
    onSuccess: (nv) => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["artifacts"] });
      onNewVersion?.(nv.id);
    },
  });

  if (v.isLoading) return <Loading />;
  if (!v.data) return <ErrorBox error={v.error} />;
  const d = v.data;
  const field = d.list_field ?? LIST_FIELD[d.artifact_type];
  const discarded = (d.content.descartados as { origem_id: string; motivo: string }[] | undefined) ?? [];
  const items = field ? ((d.content[field] as Record<string, unknown>[]) ?? []) : [];
  const evByItem = new Map<string, Evidence[]>();
  d.evidencias.forEach((e) => evByItem.set(e.item_key, [...(evByItem.get(e.item_key) ?? []), e]));

  return (
    <div className="stack">
      <div className="stack tight">
        <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
          <h2 className="grow" style={{ margin: 0 }}>{d.title}</h2>
          {d.editavel && !editing && <button className="primary" onClick={() => { setDraft(structuredClone(d.content)); setEditing(true); }}>
            <Icon name="edit" size={15} />Editar esta parte</button>}
        </div>
        <div className="row small" style={{ gap: 6 }}>
          <span className="muted">versão {d.version_no}</span><Status value={d.status} /><Status value={d.origin} />
          <Link to={`/versoes/${d.id}`}>versões anteriores</Link>
        </div>
      </div>
      {d.status === "stale" && <div className="alert warn"><Icon name="alert" />
        Confira esta parte: algo de que ela depende mudou depois que ela foi feita. Se precisar, ajuste em Editar esta parte.</div>}

      {editing ? (
        <div className="stack">
          {schema.data ? <SchemaForm schema={schema.data} value={draft} onChange={setDraft} /> : <Loading what="Carregando o formulário" />}
          <ErrorBox error={save.error} />
          <div className="row">
            <button className="primary" onClick={() => save.mutate()} disabled={save.isPending}><Icon name="check" />Salvar</button>
            <button onClick={() => setEditing(false)}>Cancelar</button>
            <span className="muted small">Sua edição vira uma nova versão; a anterior continua guardada.</span>
          </div>
        </div>
      ) : d.documento ? (
        <Markdown>{String(d.content.markdown ?? "")}</Markdown>
      ) : field ? (
        <div className="stack">
          {items.length === 0 && <div className="muted">Nenhum item.</div>}
          {items.map((it, i) => (
            <ItemCard key={String(it.id ?? i)} item={it} evidences={evByItem.get(String(it.id)) ?? []}
              onComment={onComment ? (texto) => onComment({ alvo: `${d.artifact_type}#${it.id ?? i}`, texto }) : undefined} />
          ))}
          {discarded.length > 0 && (
            <div className="item-card">
              <h3>Itens deixados de fora</h3>
              {discarded.map((x) => <div key={x.origem_id} className="small"><span className="badge warn">{x.origem_id}</span> {x.motivo}</div>)}
            </div>
          )}
        </div>
      ) : (
        <ObjectView value={d.content} onComment={onComment ? (texto) => onComment({ alvo: d.artifact_type, texto }) : undefined} />
      )}
    </div>
  );
}

function ItemCard({ item, evidences, onComment }: {
  item: Record<string, unknown>; evidences: Evidence[]; onComment?: (texto: string) => void;
}) {
  const lacunas = (item.lacunas as { campo: string; motivo: string; pergunta_sugerida?: string }[] | undefined) ?? [];
  const lacuna = item.lacuna as { motivo: string; pergunta_sugerida?: string } | null | undefined;
  return (
    <div className="item-card">
      <div className="item-head">
        {item.id ? <span className="badge item-id">{String(item.id)}</span> : null}
        {"fundamentacao_verificada" in item && (
          <span className={`badge ${item.fundamentacao_verificada ? "ok" : "warn"}`}>
            {item.fundamentacao_verificada ? "fonte conferida" : "sem fonte conferida"}</span>)}
        {item.alerta ? <span className="badge err">{String(item.alerta)}</span> : null}
        <span className="grow" />
        {onComment && <CommentButton onSubmit={onComment} />}
      </div>
      <dl className="kv">
        {Object.entries(item).filter(([k, v]) => !HIDDEN.has(k) && k !== "fundamentacao_verificada" && k !== "alerta"
          && !isEmpty(v)).map(([k, v]) => (
          <FragmentKV key={k} k={k} v={v} />
        ))}
      </dl>
      {(lacunas.length > 0 || lacuna) && (
        <div className="stack small" style={{ marginTop: 6 }}>
          {[...lacunas, ...(lacuna ? [{ campo: "resposta", ...lacuna }] : [])].map((l, i) => (
            <div key={i} className="gap"><Icon name="help" size={16} /><span>Falta informação em <strong>{fieldLabel(l.campo)}</strong>: {l.motivo}
              {l.pergunta_sugerida && <> — <em>pergunte: {l.pergunta_sugerida}</em></>}</span></div>
          ))}
        </div>
      )}
      {evidences.map((e) => <EvidenceCard key={e.id} evidence={e} />)}
    </div>
  );
}

// Campos sem conteúdo ficam fora da leitura; continuam visíveis no formulário de edição.
function isEmpty(v: unknown): boolean {
  return v == null || (typeof v === "string" && !v.trim()) || (Array.isArray(v) && v.length === 0);
}

function FragmentKV({ k, v }: { k: string; v: unknown }) {
  return <><dt>{fieldLabel(k)}</dt><dd>{show(v)}</dd></>;
}

function ObjectView({ value, onComment }: { value: Record<string, unknown>; onComment?: (t: string) => void }) {
  return (
    <div className="item-card">
      {onComment && <div className="item-head"><span className="grow" /><CommentButton onSubmit={onComment} /></div>}
      <dl className="kv">
        {Object.entries(value).filter(([k]) => k !== "lacunas").map(([k, v]) => (
          typeof v === "object" && v !== null && !Array.isArray(v)
            ? <FragmentKV key={k} k={k} v={Object.entries(v).map(([a, b]) => `${a}: ${show(b)}`).join(" · ")} />
            : <FragmentKV key={k} k={k} v={v} />
        ))}
      </dl>
    </div>
  );
}

function CommentButton({ onSubmit }: { onSubmit: (texto: string) => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  if (!open) return <button className="small" onClick={() => setOpen(true)}><Icon name="message" size={14} />Comentar</button>;
  return (
    <div className="row" style={{ flex: "1 1 100%" }}>
      <input className="grow" value={text} onChange={(e) => setText(e.target.value)} placeholder="O que precisa mudar neste item?" autoFocus />
      <button className="primary" disabled={!text.trim()} onClick={() => { onSubmit(text.trim()); setText(""); setOpen(false); }}>Adicionar</button>
      <button onClick={() => setOpen(false)}>×</button>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  OBRIGACAO_NORMATIVA: "exigência legal", RECOMENDACAO_TECNICA: "recomendação técnica", DERIVADO_VISAO: "vem da Visão",
  ELICITACAO: "conversa com as pessoas", VISAO: "pedido registrado na Visão",
};

export function EvidenceCard({ evidence }: { evidence: Evidence }) {
  const qc = useQueryClient();
  const review = useMutation({
    mutationFn: (human_status: string) => api.post(`/evidence/${evidence.id}/review`, { human_status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["version"] }),
  });
  const c = evidence.chunk;
  const meta = c?.meta ?? {};
  return (
    <details className="quote" style={{ marginTop: 8 }}>
      <summary className="row" style={{ gap: 6 }}>
        <span className="badge">{KIND_LABEL[evidence.kind.split(".").pop() ?? ""] ?? evidence.kind}</span>
        <Status value={evidence.verification} />
        <span className="small mono">{String(meta.arquivo ?? evidence.chunk_ref)}{meta.artigo ? ` · art. ${meta.artigo}` : ""}{c?.pagina ? ` · p. ${c.pagina}` : ""}</span>
        {evidence.human_status !== "pending" && <span className={`badge ${evidence.human_status === "accepted" ? "ok" : "err"}`}>{evidence.human_status === "accepted" ? "aceita" : "rejeitada"}</span>}
      </summary>
      <div className="small" style={{ marginTop: 6 }}>"{evidence.citacao}"</div>
      {c && <pre className="small" style={{ marginTop: 6, maxHeight: 240, overflow: "auto" }}>{highlight(c.texto, evidence.citacao)}</pre>}
      <div className="row" style={{ marginTop: 6 }}>
        <button className="small" onClick={() => review.mutate("accepted")}><Icon name="check" size={14} />A fonte confirma</button>
        <button className="small danger" onClick={() => review.mutate("rejected")}><Icon name="x" size={14} />Não confirma</button>
      </div>
    </details>
  );
}

function highlight(text: string, quote: string) {
  const q = quote.trim().slice(0, 80);
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return text;
  return <>{text.slice(0, i)}<mark>{text.slice(i, i + quote.length)}</mark>{text.slice(i + quote.length)}</>;
}
