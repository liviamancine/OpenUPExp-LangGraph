/** Formulário gerado a partir do JSON Schema dos tipos BAML (via Pydantic). */
import Icon from "./Icon";
import { useContext } from "react";
import { ITEM_ID, InfoTip, PART_ITEM_NOUN, PartTypeContext, Ref, usePartLabel, valueLabel } from "./ui";
import { FIELD_HELP, PART_FIELD_HELP } from "../help";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any;
type Gap = { campo: string; motivo: string; pergunta_sugerida?: string | null };
type ResolvedGap = Gap & { situacao: "resolvida" | "nao_se_aplica"; resposta?: string | null };

// Nome de um item de cada lista, para os botões dizerem o que adicionam ou removem.
const ITEM_NOUN: Record<string, string> = {
  posicionamentos: "declaração", stakeholders: "stakeholder", solicitacoes: "solicitação",
  necessidades: "necessidade", requisitos: "requisito", termos: "termo", respostas: "resposta",
  consultas: "consulta", impactos: "impacto",
};

function resolve(schema: Schema, defs: Record<string, Schema>): { schema: Schema; nullable: boolean } {
  let s = schema;
  let nullable = false;
  if (s?.anyOf) {
    const nonNull = s.anyOf.filter((x: Schema) => x.type !== "null");
    nullable = nonNull.length < s.anyOf.length;
    s = nonNull[0] ?? {};
  }
  if (s?.$ref) s = defs[s.$ref.split("/").pop()];
  return { schema: s ?? {}, nullable };
}

function emptyFor(schema: Schema, defs: Record<string, Schema>): unknown {
  const { schema: s, nullable } = resolve(schema, defs);
  if (nullable) return null;
  if (s.enum) return s.enum[0];
  if (s.type === "array") return [];
  if (s.type === "object" || s.properties) {
    const o: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(s.properties ?? {})) o[k] = emptyFor(v, defs);
    return o;
  }
  if (s.type === "boolean") return false;
  if (s.type === "integer" || s.type === "number") return 0;
  return "";
}

// Próximo ID no padrão dos existentes (ex.: POS-04 -> POS-05); vazio se a lista não tiver nenhum.
function nextId(items: unknown[]): string {
  const ids = items.map((it) => String((it as Record<string, unknown> | null)?.id ?? "").match(/^([A-Z]+)-(\d+)$/))
    .filter((m): m is RegExpMatchArray => !!m);
  if (!ids.length) return "";
  const n = Math.max(...ids.map((m) => Number(m[2]))) + 1;
  return `${ids[0][1]}-${String(n).padStart(ids[0][2].length, "0")}`;
}

function Label({ name }: { name: string }) {
  const fieldLabel = usePartLabel();
  const part = useContext(PartTypeContext);
  return <span className="label-text">{fieldLabel(name)}<InfoTip text={PART_FIELD_HELP[part]?.[name] ?? FIELD_HELP[name]} /></span>;
}

export function FieldEditor({ name, schema, value, onChange, defs, hidden, gap, depth = 0 }: {
  name: string; schema: Schema; value: unknown; onChange: (v: unknown) => void; defs: Record<string, Schema>;
  hidden: string[]; gap?: Gap; depth?: number;
}) {
  const { schema: s, nullable } = resolve(schema, defs);
  const part = useContext(PartTypeContext);
  const gapNote = gap && (
    <span className="gap small"><Icon name="help" size={14} /><span>Falta informação: {gap.motivo}
      {gap.pergunta_sugerida && <> — <em>pergunte: {gap.pergunta_sugerida}</em></>}</span></span>
  );

  if (s.enum) {
    return (
      <label><Label name={name} />
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value || (nullable ? null : ""))}>
          {nullable && <option value="">—</option>}
          {s.enum.map((v: string) => <option key={v} value={v}>{valueLabel(v)}</option>)}
        </select>
        {gapNote}
      </label>
    );
  }
  if (s.type === "array") {
    const items = (value as unknown[] | null) ?? [];
    const { schema: itemSchema } = resolve(s.items ?? {}, defs);
    if (itemSchema.type === "string" && !itemSchema.enum) {
      return (
        <label><Label name={name} /> <span className="muted">(um por linha)</span>
          <textarea value={items.join("\n")} rows={Math.max(2, items.length)}
            onChange={(e) => onChange(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean))} />
          {items.some((x) => ITEM_ID.test(String(x))) && <span className="small muted">
            {items.filter((x) => ITEM_ID.test(String(x))).map((x, i) => <span key={i}>{i > 0 && "; "}<Ref id={String(x)} /></span>)}</span>}
          {gapNote}
        </label>
      );
    }
    const noun = PART_ITEM_NOUN[part]?.[name] ?? ITEM_NOUN[name] ?? "item";
    const remove = (i: number) => {
      const id = (items[i] as Record<string, unknown> | null)?.id;
      if (window.confirm(`Remover ${noun}${id ? ` ${id}` : ""}? A remoção só vale quando você salvar a parte.`)) {
        onChange(items.filter((_, j) => j !== i));
      }
    };
    return (
      <fieldset className="item-card stack" style={{ margin: 0 }}>
        <legend className="small muted"><Label name={name} /> ({items.length})</legend>
        {items.map((it, i) => {
          const id = (it as Record<string, unknown> | null)?.id;
          return (
            <div key={i} className="stack" style={{ borderLeft: "2px solid var(--border)", paddingLeft: 8 }}>
              <FieldEditor name={`${name}[${i}]`} schema={s.items} value={it} defs={defs} hidden={hidden} depth={depth + 1}
                onChange={(v) => onChange(items.map((x, j) => (j === i ? v : x)))} />
              <button type="button" className="danger small" style={{ alignSelf: "flex-start" }} onClick={() => remove(i)}>
                <Icon name="x" size={14} />Remover {noun}{id ? ` ${id}` : ""}</button>
            </div>
          );
        })}
        <button type="button" style={{ alignSelf: "flex-start" }} onClick={() => {
          const novo = emptyFor(s.items, defs);
          if (novo && typeof novo === "object" && "id" in novo) (novo as Record<string, unknown>).id = nextId(items);
          onChange([...items, novo]);
        }}>
          <Icon name="plus" size={14} />Adicionar {noun}</button>
      </fieldset>
    );
  }
  if (s.type === "object" || s.properties) {
    const obj = (value as Record<string, unknown> | null) ?? {};
    const gaps = (obj.lacunas as Gap[] | undefined) ?? [];
    const resolved = (obj.lacunas_resolvidas as ResolvedGap[] | undefined) ?? [];
    return (
      <div className={depth > 0 ? "field-grid" : "stack"}>
        {Object.entries(s.properties ?? {}).filter(([k]) => !hidden.includes(k)).map(([k, sub]) => (
          <FieldEditor key={k} name={k} schema={sub} value={obj[k]} defs={defs} hidden={hidden} depth={depth + 1}
            gap={gaps.find((g) => g.campo === k)} onChange={(v) => onChange({ ...obj, [k]: v })} />
        ))}
        {(gaps.length > 0 || resolved.length > 0) && (
          <GapsEditor open={gaps} resolved={resolved}
            onChange={(o, r) => onChange({ ...obj, lacunas: o, lacunas_resolvidas: r })} />
        )}
      </div>
    );
  }
  if (s.type === "boolean") {
    return <label className="inline"><input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
      <Label name={name} /></label>;
  }
  const text = value === null || value === undefined ? "" : String(value);
  if (name === "id" && text) {
    return <label>Identificador<input value={text} readOnly disabled title="Gerado pela plataforma; não pode ser alterado" /></label>;
  }
  return (
    <label><Label name={name} />
      {text.length > 60 || name.includes("descricao") || name.includes("necessidade") || name.includes("requisito")
        ? <textarea value={text} onChange={(e) => onChange(e.target.value === "" && nullable ? null : e.target.value)} />
        : <input value={text} onChange={(e) => onChange(e.target.value === "" && nullable ? null : e.target.value)} />}
      {ITEM_ID.test(text) && <span className="small muted"><Ref id={text} /></span>}
      {gapNote}
    </label>
  );
}

export function SchemaForm({ schema, value, onChange, hidden = [] }: {
  schema: Schema; value: unknown; onChange: (v: unknown) => void; hidden?: string[];
}) {
  return <FieldEditor name={schema.title ?? "conteudo"} schema={schema} value={value} onChange={onChange}
    defs={schema.$defs ?? {}} hidden={hidden} />;
}

const GAP_STATE_LABEL = { aberta: "Em aberto", resolvida: "Resolvida", nao_se_aplica: "Não se aplica" };

/** "Falta informação": o Engenheiro responde (resolvida), descarta (não se aplica) ou deixa em aberto. */
function GapsEditor({ open, resolved, onChange }: {
  open: Gap[]; resolved: ResolvedGap[]; onChange: (open: Gap[], resolved: ResolvedGap[]) => void;
}) {
  const fieldLabel = usePartLabel();
  const rows: (ResolvedGap | (Gap & { situacao: "aberta"; resposta?: string | null }))[] = [
    ...open.map((g) => ({ ...g, situacao: "aberta" as const })), ...resolved];
  const update = (i: number, patch: Partial<{ situacao: string; resposta: string }>) => {
    const next = rows.map((r, j) => (j === i ? { ...r, ...patch } : r));
    const strip = ({ campo, motivo, pergunta_sugerida }: Gap): Gap => ({ campo, motivo, pergunta_sugerida });
    onChange(next.filter((r) => r.situacao === "aberta").map(strip),
      next.filter((r) => r.situacao !== "aberta") as ResolvedGap[]);
  };
  return (
    <fieldset className="item-card stack gaps-editor" style={{ margin: 0, gridColumn: "1 / -1" }}>
      <legend className="small"><Icon name="help" size={14} /> Falta informação ({open.length} em aberto)</legend>
      {rows.map((g, i) => (
        <div key={`${g.campo}-${i}`} className={`stack tight gap-row ${g.situacao}`}>
          <div className="small"><strong>{fieldLabel(g.campo)}</strong>: {g.motivo}
            {g.pergunta_sugerida && <> — <em>pergunte: {g.pergunta_sugerida}</em></>}</div>
          <div className="stack tight">
            <label style={{ maxWidth: 220 }}>Situação
              <select value={g.situacao} onChange={(e) => update(i, { situacao: e.target.value })}>
                {Object.entries(GAP_STATE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select></label>
            {g.situacao !== "aberta" && (
              <label>{g.situacao === "resolvida" ? "Resposta (o que você descobriu)" : "Por que não se aplica (opcional)"}
                <textarea rows={2} value={g.resposta ?? ""} required={g.situacao === "resolvida"}
                  onChange={(e) => update(i, { resposta: e.target.value })} /></label>
            )}
          </div>
        </div>
      ))}
    </fieldset>
  );
}
