import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Evidence, ItemComment, VersionDetail } from "../api/types";
import { SchemaForm } from "./SchemaForm";
import Icon from "./Icon";
import { useContext } from "react";
import { ErrorBox, FieldValue, InfoTip, LabelsContext, Loading, Markdown, PartTypeContext, Ref, Status, show, usePartLabel } from "./ui";
import { FIELD_HELP, ID_HELP, PART_FIELD_HELP, PART_HELP } from "../help";

function usePartHelp(): (k: string) => string | undefined {
  const part = useContext(PartTypeContext);
  return (k) => PART_FIELD_HELP[part]?.[k] ?? FIELD_HELP[k];
}

const LIST_FIELD: Record<string, string> = {
  "vision.stakeholders": "stakeholders", "vision.stakeholder_needs": "solicitacoes", "vision.domain_terms": "termos",
  glossary: "termos", "vision.explainability_needs": "necessidades", "vision.positioning": "posicionamentos",
  "vision.complementary_requirements": "requisitos", "vision.limits": "respostas", "vision.reference_queries": "consultas",
};
const HIDDEN = new Set(["id", "lacunas", "origem", "evidencias", "lacuna", "baseada_em", "descartados"]);
// Campos que valem para todos os itens da parte: aparecem uma vez, no topo, e são editados uma vez.
const SHARED_FIELDS: Record<string, string[]> = { "vision.positioning": ["nome_produto", "categoria_produto"] };
// Campos mantidos pela plataforma (rastreabilidade, pontos em aberto): ficam fora do formulário, mas são preservados.
const SYSTEM_FIELDS = ["lacunas", "lacuna", "origem", "baseada_em", "evidencias", "fundamentacao_verificada", "alerta", "descartados"];

// Campos de manifestos antigos: saem do formulário quando estão vazios (a partir do 0.5.0, o perfil
// do Posicionamento não aponta para stakeholder nem necessidades, e a Definição não traz a Declaração do Problema).
const LEGACY_FIELDS: Record<string, string[]> = {
  "vision.positioning": ["stakeholder_id", "need_ids"],
  "vision.problem": ["declaracao_problema"],
  "vision.explainability_needs": ["aspecto_associado"],
};

type Item = Record<string, unknown>;

// Ordem dos campos como no contrato (e no modelo do documento): o banco guarda o JSON com as
// chaves reordenadas, então a leitura não pode confiar na ordem em que elas chegam.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function fieldOrder(schema: any, listField?: string): string[] {
  if (!schema) return [];
  const defs = schema.$defs ?? {};
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const deref = (x: any) => (x?.$ref ? defs[x.$ref.split("/").pop()] : x) ?? {};
  const target = listField ? deref(deref(schema.properties?.[listField]).items) : schema;
  return Object.keys(target.properties ?? {});
}

function ordered(obj: Item, order: string[]): [string, unknown][] {
  const rank = (k: string) => (order.indexOf(k) < 0 ? order.length : order.indexOf(k));
  return Object.entries(obj).sort(([a], [b]) => rank(a) - rank(b));
}

function sharedValue(items: Item[], k: string): unknown {
  return items.map((it) => it[k]).find((x) => !isEmpty(x)) ?? null;
}

export default function ArtifactView({ versionId, onComment, onNewVersion }: {
  versionId: string; onComment?: (c: ItemComment) => void; onNewVersion?: (id: string) => void;
}) {
  const qc = useQueryClient();
  const v = useQuery({ queryKey: ["version", versionId], queryFn: () => api.get<VersionDetail>(`/artifact-versions/${versionId}`) });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<unknown>(null);
  const schema = useQuery({
    queryKey: ["schema", v.data?.artifact_type], enabled: !!v.data, staleTime: Infinity,
    queryFn: () => api.get<Record<string, unknown>>(`/artifact-types/${v.data!.artifact_type}/schema`),
  });
  const save = useMutation({
    mutationFn: () => api.post<{ id: string }>(`/artifact-versions/${versionId}/edits`, { content: withShared(draft) }),
    onSuccess: (nv) => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["artifacts"] });
      onNewVersion?.(nv.id);
    },
  });

  // Os campos comuns valem para todos os itens, inclusive os adicionados durante a edição.
  function withShared(content: unknown): unknown {
    const type = v.data?.artifact_type ?? "";
    const list = v.data?.list_field ?? LIST_FIELD[type];
    const fields = SHARED_FIELDS[type] ?? [];
    const rows = list ? ((content as Item)?.[list] as Item[] | undefined) : undefined;
    if (!list || !fields.length || !rows) return content;
    const values = Object.fromEntries(fields.map((k) => [k, sharedValue(rows, k)]));
    return { ...(content as Item), [list]: rows.map((it) => ({ ...it, ...values })) };
  }

  if (v.isLoading) return <Loading />;
  if (!v.data) return <ErrorBox error={v.error} />;
  const d = v.data;
  const field = d.list_field ?? LIST_FIELD[d.artifact_type];
  const discarded = (d.content.descartados as { origem_id: string; motivo: string }[] | undefined) ?? [];
  const items = field ? ((d.content[field] as Item[]) ?? []) : [];
  const shared = SHARED_FIELDS[d.artifact_type] ?? [];
  const help = PART_HELP[d.artifact_type];
  const order = fieldOrder(schema.data, field);
  const legacy = (LEGACY_FIELDS[d.artifact_type] ?? []).filter((k) =>
    field ? items.every((it) => isEmpty(it[k])) : isEmpty(d.content[k]));
  const evByItem = new Map<string, Evidence[]>();
  d.evidencias.forEach((e) => evByItem.set(e.item_key, [...(evByItem.get(e.item_key) ?? []), e]));

  return (
    <PartTypeContext.Provider value={d.artifact_type}>
    <LabelsContext.Provider value={d.rotulos ?? {}}>
    <div className="stack">
      <div className="stack tight">
        <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
          <h2 className="grow" style={{ margin: 0 }}>{d.title}<InfoTip text={help?.texto} source={help?.fonte} /></h2>
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
          {field && shared.length > 0 && (
            <SharedFieldsEditor fields={shared} items={((draft as Item)?.[field] as Item[]) ?? []}
              onChange={(next) => setDraft({ ...(draft as Item), [field]: next })} />
          )}
          {schema.data
            ? <SchemaForm schema={schema.data} value={draft} onChange={setDraft} hidden={[...SYSTEM_FIELDS, ...shared, ...legacy]} />
            : <Loading what="Carregando o formulário" />}
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
          {items.length === 0 && (d.content.desligado
            ? <div className="alert info small"><Icon name="info" />{String(d.content.motivo ?? "Parte desligada nesta instalação.")}</div>
            : <div className="muted">Nenhum item.</div>)}
          {shared.length > 0 && items.length > 0 && <SharedFieldsView fields={shared} items={items} />}
          {items.map((it, i) => (
            <ItemCard key={String(it.id ?? i)} item={it} hide={shared} order={order} evidences={evByItem.get(String(it.id)) ?? []}
              onComment={onComment ? (texto) => onComment({ alvo: `${d.artifact_type}#${it.id ?? i}`, texto }) : undefined} />
          ))}
          {discarded.length > 0 && (
            <div className="item-card">
              <h3>Itens deixados de fora</h3>
              {discarded.map((x) => <div key={x.origem_id} className="small"><Ref id={x.origem_id} /> — {x.motivo}</div>)}
            </div>
          )}
        </div>
      ) : (
        <ObjectView value={d.content} order={order} onComment={onComment ? (texto) => onComment({ alvo: d.artifact_type, texto }) : undefined} />
      )}
    </div>
    </LabelsContext.Provider>
    </PartTypeContext.Provider>
  );
}

type Gap = { campo: string; motivo: string; pergunta_sugerida?: string };

function GapLine({ gap }: { gap: Gap }) {
  const fieldLabel = usePartLabel();
  return <div className="gap"><Icon name="help" size={16} /><span>Falta informação em <strong>{fieldLabel(gap.campo)}</strong>: {gap.motivo}
    {gap.pergunta_sugerida && <> — <em>pergunte: {gap.pergunta_sugerida}</em></>}</span></div>;
}

function SharedFieldsView({ fields, items }: { fields: string[]; items: Item[] }) {
  const gaps = fields.filter((k) => isEmpty(sharedValue(items, k)))
    .map((k) => items.flatMap((it) => (it.lacunas as Gap[] | undefined) ?? []).find((g) => g.campo === k))
    .filter((g): g is Gap => !!g);
  return (
    <div className="item-card">
      <div className="small muted">Vale para todas as declarações abaixo</div>
      <dl className="kv">
        {fields.map((k) => <FragmentKV key={k} k={k} v={sharedValue(items, k)} />)}
      </dl>
      {gaps.length > 0 && <div className="stack small" style={{ marginTop: 6 }}>{gaps.map((g) => <GapLine key={g.campo} gap={g} />)}</div>}
    </div>
  );
}

function SharedFieldsEditor({ fields, items, onChange }: { fields: string[]; items: Item[]; onChange: (items: Item[]) => void }) {
  const fieldLabel = usePartLabel();
  const help = usePartHelp();
  return (
    <fieldset className="item-card stack" style={{ margin: 0 }}>
      <legend className="small muted">Vale para todas as declarações</legend>
      {fields.map((k) => {
        const value = sharedValue(items, k);
        return (
          <label key={k}><span className="label-text">{fieldLabel(k)}<InfoTip text={help(k)} /></span>
            <input value={value == null ? "" : String(value)}
              onChange={(e) => onChange(items.map((it) => ({ ...it, [k]: e.target.value || null })))} />
          </label>
        );
      })}
    </fieldset>
  );
}

function ItemCard({ item, hide = [], order = [], evidences, onComment }: {
  item: Item; hide?: string[]; order?: string[]; evidences: Evidence[]; onComment?: (texto: string) => void;
}) {
  const lacunas = ((item.lacunas as Gap[] | undefined) ?? []).filter((g) => !hide.includes(g.campo));
  const lacuna = item.lacuna as { motivo: string; pergunta_sugerida?: string } | null | undefined;
  return (
    <div className="item-card">
      <div className="item-head">
        {item.id ? <span className="badge item-id">{String(item.id)}
          <InfoTip text={ID_HELP[String(item.id).split("-")[0]]} /></span> : null}
        <SourceBadge item={item} evidences={evidences} />
        {item.alerta ? <span className="badge err">{String(item.alerta)}</span> : null}
        <span className="grow" />
        {onComment && <CommentButton onSubmit={onComment} />}
      </div>
      <dl className="kv">
        {ordered(item, order).filter(([k, v]) => !HIDDEN.has(k) && !hide.includes(k) && k !== "fundamentacao_verificada"
          && k !== "alerta" && !isEmpty(v)).map(([k, v]) => (
          <FragmentKV key={k} k={k} v={v} />
        ))}
      </dl>
      {(lacunas.length > 0 || lacuna) && (
        <div className="stack small" style={{ marginTop: 6 }}>
          {[...lacunas, ...(lacuna ? [{ campo: "resposta", ...lacuna }] : [])].map((l, i) => <GapLine key={i} gap={l} />)}
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
  const fieldLabel = usePartLabel();
  const help = usePartHelp();
  return <><dt>{fieldLabel(k)}<InfoTip text={help(k)} /></dt><dd><FieldValue value={v} /></dd></>;
}

// "2 de 6 citações conferidas": quantas citações foram achadas, palavra por palavra, na fonte.
function SourceBadge({ item, evidences }: { item: Item; evidences: Evidence[] }) {
  if (evidences.length) {
    const ok = evidences.filter((e) => e.verification === "verified").length;
    const tone = ok === evidences.length ? "ok" : ok ? "warn" : "err";
    return <span className={`badge ${tone}`} title="Citação conferida: o trecho foi achado, palavra por palavra, no documento.">
      {ok} de {evidences.length} {evidences.length === 1 ? "citação conferida" : "citações conferidas"}</span>;
  }
  if (!("fundamentacao_verificada" in item)) return null;
  return <span className={`badge ${item.fundamentacao_verificada ? "ok" : "warn"}`}>
    {item.fundamentacao_verificada ? "fonte conferida" : "sem fonte conferida"}</span>;
}

function ObjectView({ value, order = [], onComment }: { value: Item; order?: string[]; onComment?: (t: string) => void }) {
  return (
    <div className="item-card">
      {onComment && <div className="item-head"><span className="grow" /><CommentButton onSubmit={onComment} /></div>}
      <dl className="kv">
        {ordered(value, order).filter(([k, v]) => k !== "lacunas" && !isEmpty(v)).map(([k, v]) => (
          typeof v === "object" && v !== null && !Array.isArray(v)
            ? <FragmentKV key={k} k={k} v={Object.entries(v).map(([a, b]) => `${a}: ${show(b)}`).join(" · ")} />
            : <FragmentKV key={k} k={k} v={v} />
        ))}
      </dl>
      {((value.lacunas as Gap[] | undefined) ?? []).length > 0 && (
        <div className="stack small" style={{ marginTop: 6 }}>
          {(value.lacunas as Gap[]).map((g, i) => <GapLine key={i} gap={g} />)}
        </div>
      )}
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

// Fala de quem conduz a conversa ("E:", "Entrevistadora:"): não é evidência do que o stakeholder disse.
const INTERVIEWER = /^\s*["“]?\s*(E|P|Entrevistador[a]?|Pesquisador[a]?|Moderador[a]?)\s*[:\-–]/i;

export function EvidenceCard({ evidence }: { evidence: Evidence }) {
  const qc = useQueryClient();
  const review = useMutation({
    mutationFn: (human_status: string) => api.post(`/evidence/${evidence.id}/review`, { human_status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["version"] }),
  });
  const c = evidence.chunk;
  const meta = c?.meta ?? {};
  const arquivo = String(meta.arquivo ?? evidence.chunk_ref);
  const docUrl = c?.documento_id
    ? `/documentos/${c.documento_id}?trecho=${encodeURIComponent(evidence.citacao.slice(0, 160))}` : null;
  return (
    <div className="quote citation">
      <div className="row small" style={{ gap: 6 }}>
        <span className="badge">{KIND_LABEL[evidence.kind.split(".").pop() ?? ""] ?? evidence.kind}</span>
        <Status value={evidence.verification} />
        {evidence.human_status !== "pending" && <span className={`badge ${evidence.human_status === "accepted" ? "ok" : "err"}`}>
          {evidence.human_status === "accepted" ? "você confirmou" : "você não confirmou"}</span>}
      </div>
      <blockquote>"{evidence.citacao}"</blockquote>
      {INTERVIEWER.test(evidence.citacao) && <div className="alert warn small"><Icon name="alert" size={14} />
        Este trecho parece ser a fala de quem conduziu a conversa, não do stakeholder. Confira antes de aceitar.</div>}
      {evidence.verification === "unverified_quote" && <div className="muted small">
        A IA pode ter mudado as palavras: o trecho não foi achado igual no documento. Abra o documento para conferir.</div>}
      <div className="row small" style={{ gap: 8 }}>
        {docUrl
          ? <Link to={docUrl} target="_blank" rel="noopener"><Icon name="file" size={14} /> Abrir {arquivo}{meta.artigo ? ` · art. ${meta.artigo}` : ""}{c?.pagina ? ` · p. ${c.pagina}` : ""}</Link>
          : <span className="mono">{arquivo}</span>}
        <span className="grow" />
        <button className="small" onClick={() => review.mutate("accepted")}><Icon name="check" size={14} />A fonte confirma</button>
        <button className="small danger" onClick={() => review.mutate("rejected")}><Icon name="x" size={14} />Não confirma</button>
      </div>
    </div>
  );
}

