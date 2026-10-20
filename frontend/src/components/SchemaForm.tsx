/** Formulário gerado a partir do JSON Schema dos tipos BAML (via Pydantic). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any;

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

export function FieldEditor({ name, schema, value, onChange, defs, depth = 0 }: {
  name: string; schema: Schema; value: unknown; onChange: (v: unknown) => void; defs: Record<string, Schema>; depth?: number;
}) {
  const { schema: s, nullable } = resolve(schema, defs);
  const label = s.title ?? schema.title ?? name;
  const help = schema.description ?? s.description;

  if (s.enum) {
    return (
      <label title={help}>{label}
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value || (nullable ? null : ""))}>
          {nullable && <option value="">—</option>}
          {s.enum.map((v: string) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
    );
  }
  if (s.type === "array") {
    const items = (value as unknown[] | null) ?? [];
    const { schema: itemSchema } = resolve(s.items ?? {}, defs);
    if (itemSchema.type === "string" && !itemSchema.enum) {
      return (
        <label title={help}>{label} <span className="muted">(um por linha)</span>
          <textarea value={items.join("\n")} rows={Math.max(2, items.length)}
            onChange={(e) => onChange(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean))} />
        </label>
      );
    }
    return (
      <fieldset className="item-card stack" style={{ margin: 0 }}>
        <legend className="small muted">{label} ({items.length})</legend>
        {items.map((it, i) => (
          <div key={i} className="stack" style={{ borderLeft: "2px solid var(--border)", paddingLeft: 8 }}>
            <FieldEditor name={`${name}[${i}]`} schema={s.items} value={it} defs={defs} depth={depth + 1}
              onChange={(v) => onChange(items.map((x, j) => (j === i ? v : x)))} />
            <button type="button" className="danger small" onClick={() => onChange(items.filter((_, j) => j !== i))}>Remover</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...items, emptyFor(s.items, defs)])}>Adicionar</button>
      </fieldset>
    );
  }
  if (s.type === "object" || s.properties) {
    const obj = (value as Record<string, unknown> | null) ?? {};
    return (
      <div className={depth > 0 ? "field-grid" : "stack"}>
        {Object.entries(s.properties ?? {}).map(([k, sub]) => (
          <FieldEditor key={k} name={k} schema={sub} value={obj[k]} defs={defs} depth={depth + 1}
            onChange={(v) => onChange({ ...obj, [k]: v })} />
        ))}
      </div>
    );
  }
  if (s.type === "boolean") {
    return <label className="inline"><input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />{label}</label>;
  }
  const text = value === null || value === undefined ? "" : String(value);
  const readOnly = name === "id";
  return (
    <label title={help}>{label}
      {text.length > 60 || name.includes("descricao") || name.includes("necessidade") || name.includes("requisito")
        ? <textarea value={text} onChange={(e) => onChange(e.target.value === "" && nullable ? null : e.target.value)} />
        : <input value={text} readOnly={readOnly} onChange={(e) => onChange(e.target.value === "" && nullable ? null : e.target.value)} />}
    </label>
  );
}

export function SchemaForm({ schema, value, onChange }: { schema: Schema; value: unknown; onChange: (v: unknown) => void }) {
  return <FieldEditor name={schema.title ?? "conteudo"} schema={schema} value={value} onChange={onChange} defs={schema.$defs ?? {}} />;
}
