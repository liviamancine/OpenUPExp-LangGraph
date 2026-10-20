import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AdminModel, AdminOverview, AdminProfile, ConnResult } from "../api/types";
import Icon from "../components/Icon";
import { Empty, ErrorBox, Hint, Loading, fmtDate } from "../components/ui";

const PARAM_LABEL: Record<string, string> = {
  temperature: "temperatura", max_tokens: "limite de resposta", num_ctx: "contexto", think: "raciocínio",
};

function slugify(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").slice(0, 60);
}

export default function AdminModelsPage() {
  const qc = useQueryClient();
  const overview = useQuery({
    queryKey: ["admin-llm"], queryFn: () => api.get<AdminOverview>("/admin/llm"),
    refetchInterval: (q) => (q.state.data?.modelos.some((m) => m.perfis.some((p) => p.compat?.status === "na_fila")) ? 3000 : false),
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin-llm"] });
    qc.invalidateQueries({ queryKey: ["llm-profiles"] });
  };
  const [creating, setCreating] = useState(false);

  if (overview.isLoading) return <Loading what="Carregando os modelos" />;
  if (!overview.data) return <ErrorBox error={overview.error} />;
  const o = overview.data;

  return (
    <div className="stack">
      <section className="hero">
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow">
            <h1>Modelos de IA</h1>
            <div className="subtitle">Cadastre os modelos que podem executar as etapas, teste a conexão e a
              compatibilidade com os formatos da plataforma, e escolha o padrão. O modelo local é a referência
              para comparação e não pode ser alterado.</div>
          </div>
          <button className="light big" onClick={() => setCreating(true)}><Icon name="plus" />Cadastrar modelo</button>
        </div>
      </section>

      <div className="grid-2">
        <Hint tone={o.modelo_local_ligado ? "ok" : "warn"} icon={o.modelo_local_ligado ? "checkCircle" : "info"}>
          {o.modelo_local_ligado
            ? "Modelo local ligado nesta instalação."
            : <>Modelo local desligado nesta instalação. Para ligar: <code>LOCAL_LLM_ENABLED=true</code> e{" "}
              <code>docker compose --profile local-llm up -d</code>.</>}
        </Hint>
        <details className="card">
          <summary><strong>Servidores permitidos</strong> <span className="muted small">({o.servidores_permitidos.length})</span></summary>
          <div className="small muted" style={{ marginTop: 8 }}>Os agentes enviam trechos dos documentos do projeto ao modelo.
            Por isso só estes servidores podem ser cadastrados (variável <code>LLM_ALLOWED_HOSTS</code> da instalação):</div>
          <div className="row small" style={{ marginTop: 8, gap: 6 }}>{o.servidores_permitidos.map((h) => <span key={h} className="badge">{h}</span>)}</div>
        </details>
      </div>

      {creating && <NewModel o={o} onDone={() => { setCreating(false); refresh(); }} onCancel={() => setCreating(false)} />}
      {o.modelos.map((m) => <ModelCard key={m.id} m={m} onChange={refresh} />)}
    </div>
  );
}

function NewModel({ o, onDone, onCancel }: { o: AdminOverview; onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({ nome: "", provider: "openai-generic", base_url: "", model: "", api_key_env: "" });
  const needsUrl = form.provider === "ollama" || form.provider === "openai-generic";
  const create = useMutation({
    mutationFn: () => api.post("/admin/llm/models", {
      ...form, slug: slugify(form.nome), base_url: needsUrl ? form.base_url : null,
      api_key_env: form.api_key_env || null, params: { temperature: 0 },
    }),
    onSuccess: onDone,
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <form className="card stack" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <div className="card-head"><span className="icon-bubble"><Icon name="plus" /></span><h2>Cadastrar modelo</h2></div>
      <div className="grid-2">
        <label>Nome<input value={form.nome} onChange={set("nome")} required placeholder="ex.: Qwen3 8B no servidor do laboratório" /></label>
        <label>Provedor<select value={form.provider} onChange={set("provider")}>
          {Object.entries(o.provedores).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></label>
        {needsUrl && <label>Endereço do servidor<input value={form.base_url} onChange={set("base_url")} required
          placeholder={form.provider === "ollama" ? "http://servidor:11434" : "https://servidor/v1"} /></label>}
        <label>Modelo no provedor<input value={form.model} onChange={set("model")} required placeholder="ex.: qwen3:8b" /></label>
        <label>Variável com a chave {needsUrl ? "(opcional)" : ""}<input value={form.api_key_env} onChange={set("api_key_env")}
          placeholder="ex.: MISTRAL_API_KEY" /></label>
      </div>
      <div className="muted small">A chave em si fica no servidor (arquivo <code>.env</code>); aqui você informa só o nome da variável.
        O modelo começa com um perfil desabilitado: teste a compatibilidade antes de habilitá-lo.</div>
      <ErrorBox error={create.error} />
      <div className="row">
        <button className="primary" disabled={create.isPending || !form.nome}><Icon name="check" />Cadastrar</button>
        <button type="button" className="ghost" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}

function ModelCard({ m, onChange }: { m: AdminModel; onChange: () => void }) {
  const [conn, setConn] = useState<ConnResult | null>(m.conexao);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newProfile, setNewProfile] = useState(false);
  const test = useMutation({ mutationFn: () => api.post<ConnResult>(`/admin/llm/models/${m.id}/test-connection`),
    onSuccess: (r) => { setConn(r); onChange(); } });
  const toggle = useMutation({ mutationFn: () => api.patch(`/admin/llm/models/${m.id}`, { enabled: !m.habilitado }), onSuccess: onChange });
  const remove = useMutation({ mutationFn: () => api.del(`/admin/llm/models/${m.id}`), onSuccess: onChange });
  const shown = conn ?? m.conexao;

  return (
    <div className="card stack">
      <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
        <span className="icon-bubble" style={m.local ? { background: "var(--ok-soft)", color: "var(--ok)" } : undefined}>
          <Icon name={m.local ? "lock" : "sparkles"} /></span>
        <span className="grow">
          <div className="row" style={{ gap: 8 }}>
            <h2 style={{ margin: 0 }}>{m.nome}</h2>
            {m.local && <span className="badge ok">referência local</span>}
            {m.protegido && <span className="badge"><Icon name="lock" size={11} />protegido</span>}
            {!m.habilitado && <span className="badge warn">desligado</span>}
            {m.chave_configurada === false && <span className="badge err">sem chave no servidor</span>}
          </div>
          <div className="muted small">{m.provider} · <span className="mono">{m.model}</span>{m.endereco && <> · {m.endereco}</>}
            {m.api_key_env && <> · chave em <span className="mono">{m.api_key_env}</span></>}</div>
          {m.descricao && <div className="small">{m.descricao}</div>}
        </span>
        <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
          <button className="small" onClick={() => test.mutate()} disabled={test.isPending}>
            <Icon name="zap" size={14} />{test.isPending ? "Testando…" : "Testar conexão"}</button>
          {!m.protegido && <button className="small" onClick={() => toggle.mutate()} disabled={toggle.isPending}>
            {m.habilitado ? "Desligar" : "Ligar"}</button>}
          {!m.protegido && (confirmDelete
            ? <><button className="small danger" onClick={() => remove.mutate()}>Confirmar exclusão</button>
              <button className="small ghost" onClick={() => setConfirmDelete(false)}>Cancelar</button></>
            : <button className="small ghost" onClick={() => setConfirmDelete(true)} aria-label="Excluir modelo"><Icon name="archive" size={14} /></button>)}
        </div>
      </div>
      {shown && (
        <div className={`alert small ${shown.ok ? (shown.modelo_encontrado === false ? "warn" : "ok") : "err"}`}>
          <Icon name={shown.ok ? "checkCircle" : "xCircle"} />
          <div>{shown.detalhe} <span className="muted">({shown.latency_ms} ms · {fmtDate(shown.at)})</span>
            {shown.modelos && shown.modelos.length > 0 && <details><summary>Modelos no servidor ({shown.modelos.length})</summary>
              <div className="mono tiny">{shown.modelos.join(", ")}</div></details>}</div>
        </div>
      )}
      <ErrorBox error={test.error ?? toggle.error ?? remove.error} />

      <div className="stack tight">
        <div className="row"><h3 className="grow" style={{ margin: 0 }}>Perfis de uso</h3>
          {!m.protegido && <button className="small" onClick={() => setNewProfile(true)}><Icon name="plus" size={14} />Novo perfil</button>}</div>
        {m.perfis.map((p) => <ProfileRow key={p.id} p={p} onChange={onChange} />)}
        {m.perfis.length === 0 && <Empty icon="settings">Nenhum perfil.</Empty>}
        {newProfile && <NewProfile model={m} onDone={() => { setNewProfile(false); onChange(); }} onCancel={() => setNewProfile(false)} />}
      </div>
    </div>
  );
}

function ProfileRow({ p, onChange }: { p: AdminProfile; onChange: () => void }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const compat = useMutation({ mutationFn: () => api.post(`/admin/llm/profiles/${p.id}/test-compat`), onSuccess: onChange });
  const toggle = useMutation({ mutationFn: () => api.patch(`/admin/llm/profiles/${p.id}`, { enabled: !p.habilitado }), onSuccess: onChange });
  const makeDefault = useMutation({ mutationFn: () => api.post(`/admin/llm/profiles/${p.id}/default`), onSuccess: onChange });
  const remove = useMutation({ mutationFn: () => api.del(`/admin/llm/profiles/${p.id}`), onSuccess: onChange });
  const c = p.compat;
  const running = c?.status === "na_fila";

  return (
    <div className="item-card stack tight">
      <div className="row" style={{ gap: 8 }}>
        <strong className="grow">{p.nome}</strong>
        {p.padrao_efetivo && <span className="badge ok"><Icon name="flag" size={11} />padrão das novas etapas</span>}
        {p.padrao_marcado && !p.padrao_efetivo && <span className="badge warn" title="Indisponível agora; usando a nuvem com reserva">marcado como padrão</span>}
        <span className={`badge ${p.habilitado ? "completed" : ""}`}>{p.habilitado ? "habilitado" : "desabilitado"}</span>
      </div>
      <div className="row small" style={{ gap: 6 }}>
        {Object.entries(p.params).map(([k, v]) => <span key={k} className="badge">{PARAM_LABEL[k] ?? k}: {String(v)}</span>)}
        {Object.keys(p.params).length === 0 && <span className="muted">parâmetros do provedor</span>}
      </div>
      <div className={`small ${c ? "" : "muted"}`}>
        {!c ? "Compatibilidade ainda não testada."
          : running ? <span className="row" style={{ gap: 8 }}><span className="spinner" />Teste de compatibilidade na fila… (com o modelo local pode levar alguns minutos)</span>
          : <span className="row" style={{ gap: 6, color: c.ok ? "var(--ok)" : "var(--err)" }}>
              <Icon name={c.ok ? "checkCircle" : "xCircle"} size={15} />{c.ok ? "Compatível" : "Incompatível"}: {c.detalhe}
              <span className="muted">({((c.latency_ms ?? 0) / 1000).toFixed(1)} s{c.output_tokens ? ` · ${c.output_tokens} tokens` : ""} · {fmtDate(c.at)})</span></span>}
      </div>
      <div className="row" style={{ gap: 6 }}>
        <button className="small" onClick={() => compat.mutate()} disabled={running || compat.isPending}>
          <Icon name="checkCircle" size={14} />Testar compatibilidade</button>
        {!p.protegido && <button className="small" onClick={() => toggle.mutate()} disabled={toggle.isPending}>
          {p.habilitado ? "Desabilitar" : "Habilitar"}</button>}
        {!p.padrao_marcado && p.habilitado && <button className="small" onClick={() => makeDefault.mutate()}>
          <Icon name="flag" size={14} />Tornar padrão</button>}
        {!p.protegido && (confirmDelete
          ? <><button className="small danger" onClick={() => remove.mutate()}>Confirmar exclusão</button>
            <button className="small ghost" onClick={() => setConfirmDelete(false)}>Cancelar</button></>
          : <button className="small ghost" onClick={() => setConfirmDelete(true)} aria-label="Excluir perfil"><Icon name="archive" size={14} /></button>)}
      </div>
      <ErrorBox error={compat.error ?? toggle.error ?? makeDefault.error ?? remove.error} />
    </div>
  );
}

function NewProfile({ model, onDone, onCancel }: { model: AdminModel; onDone: () => void; onCancel: () => void }) {
  const [nome, setNome] = useState("");
  const [temperature, setTemperature] = useState("0");
  const [maxTokens, setMaxTokens] = useState("");
  const create = useMutation({
    mutationFn: () => api.post(`/admin/llm/models/${model.id}/profiles`, {
      nome, slug: slugify(`${model.slug}-${nome}`),
      params: { temperature: Number(temperature), ...(maxTokens ? { max_tokens: Number(maxTokens) } : {}) },
    }),
    onSuccess: onDone,
  });
  return (
    <form className="item-card stack tight" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <div className="grid-2">
        <label>Nome do perfil<input value={nome} onChange={(e) => setNome(e.target.value)} required placeholder="ex.: criativo" /></label>
        <label>Temperatura (0 a 2)<input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(e.target.value)} /></label>
        <label>Limite de resposta em tokens (opcional)<input type="number" min="1" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} /></label>
      </div>
      <ErrorBox error={create.error} />
      <div className="row"><button className="primary small" disabled={create.isPending}>Criar perfil</button>
        <button type="button" className="ghost small" onClick={onCancel}>Cancelar</button></div>
    </form>
  );
}
