import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ProjectDetail, RunSummary, User } from "../api/types";
import { ErrorBox, Loading, PHASE_NAMES, Status, Tabs, fmtDate } from "../components/ui";

const KINDS = [
  { id: "escopo", label: "Escopo do projeto" },
  { id: "lei", label: "Lei / norma" },
  { id: "manual", label: "Manual" },
  { id: "academico", label: "Acadêmico / literatura" },
  { id: "elicitacao", label: "Material de elicitação (entrevistas, workshops…)" },
];

const STRATEGIES = [
  { id: "D", label: "D — Híbrida (padrão)" },
  { id: "C", label: "C — Contratos estruturados" },
  { id: "A", label: "A — Contexto integral" },
];

export default function ProjectPage() {
  const { projectId = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"execucoes" | "fontes" | "membros">("execucoes");
  const project = useQuery({
    queryKey: ["project", projectId], queryFn: () => api.get<ProjectDetail>(`/projects/${projectId}`),
    refetchInterval: (q) => (q.state.data?.corpora.some((c) => c.status === "building") ? 3000 : false),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["project", projectId] });

  const [phase, setPhase] = useState("1");
  const [baseRun, setBaseRun] = useState("");
  const [strategy, setStrategy] = useState("D");
  const [gateway, setGateway] = useState("baml");
  const start = useMutation({
    mutationFn: () => api.post<RunSummary>(`/projects/${projectId}/runs`,
      { phase, context_strategy: strategy, agent_gateway: gateway, base_run_id: phase !== "1" ? baseRun : null }),
    onSuccess: (r) => navigate(`/execucoes/${r.id}`),
  });

  const [kind, setKind] = useState("escopo");
  const [files, setFiles] = useState<FileList | null>(null);
  const upload = useMutation({
    mutationFn: async () => {
      for (const f of Array.from(files ?? [])) {
        const form = new FormData();
        form.append("file", f);
        form.append("source_kind", kind);
        await api.upload(`/projects/${projectId}/sources`, form);
      }
    },
    onSuccess: () => { setFiles(null); refresh(); },
  });
  const index = useMutation({ mutationFn: () => api.post(`/projects/${projectId}/corpus`), onSuccess: () => setTimeout(refresh, 1500) });
  const deactivate = useMutation({ mutationFn: (id: string) => api.del(`/projects/${projectId}/sources/${id}`), onSuccess: refresh });

  if (project.isLoading) return <Loading />;
  if (!project.data) return <ErrorBox error={project.error} />;
  const p = project.data;
  const isEngineer = p.meu_papel === "requirements_engineer" || p.meu_papel === "admin";
  const hasScope = p.fontes.some((f) => f.source_kind === "escopo" && f.ativo);
  const ready = p.corpora.find((c) => c.status === "ready");
  const previousPhase = String(Number(phase) - 1);
  const baseRuns = p.execucoes.filter((r) => r.phase === previousPhase && r.status === "completed");
  const elicitationDocs = p.fontes.filter((f) => f.source_kind === "elicitacao" && f.ativo).length;

  return (
    <div className="stack">
      <div className="row">
        <div className="grow">
          <h1>{p.nome}</h1>
          <div className="muted">{p.dominio ?? "domínio não informado"} · seu papel: {p.meu_papel}</div>
        </div>
      </div>
      <Tabs value={tab} onChange={setTab} items={[
        { id: "execucoes", label: `Execuções (${p.execucoes.length})` },
        { id: "fontes", label: `Fontes (${p.fontes.length})` },
        { id: "membros", label: `Membros (${p.membros.length})` },
      ]} />

      {tab === "execucoes" && (
        <div className="split">
          <div className="card">
            <table>
              <thead><tr><th>Execução</th><th>Fase</th><th>Estratégia</th><th>Gateway</th><th>Status</th><th>Criada</th></tr></thead>
              <tbody>
                {p.execucoes.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/execucoes/${r.id}`} className="mono">{r.id.slice(0, 8)}</Link></td>
                    <td>{r.phase} {PHASE_NAMES[r.phase] ?? ""}</td><td>{r.context_strategy}</td><td>{r.agent_gateway}</td>
                    <td><Status value={r.status} /> {r.current_task && <span className="muted small">{r.current_task}</span>}</td>
                    <td className="muted">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
                {p.execucoes.length === 0 && <tr><td colSpan={6} className="muted">Nenhuma execução.</td></tr>}
              </tbody>
            </table>
          </div>
          {isEngineer && (
            <form className="card stack" onSubmit={(e) => { e.preventDefault(); start.mutate(); }}>
              <h2>Iniciar execução</h2>
              <label>Fase
                <select value={phase} onChange={(e) => { setPhase(e.target.value); setBaseRun(""); }}>
                  <option value="1">1 — Define Explainability Vision</option>
                  <option value="2">2 — Elicit Explainability Requirements</option>
                  <option value="3">3 — Analyze Explainability Requirements</option>
                </select>
              </label>
              {phase !== "1" && (
                <>
                  <label>Execução aprovada de base (Fase {previousPhase} — {PHASE_NAMES[previousPhase]})
                    <select value={baseRun} onChange={(e) => setBaseRun(e.target.value)} required>
                      <option value="">—</option>
                      {baseRuns.map((r) => <option key={r.id} value={r.id}>{r.id.slice(0, 8)} · {fmtDate(r.created_at)} · estratégia {r.context_strategy}</option>)}
                    </select>
                  </label>
                  {baseRuns.length === 0 && <div className="alert warn">Conclua e aprove uma execução da Fase {previousPhase} antes.</div>}
                </>
              )}
              {phase === "2" && (
                <>
                  <div className="alert info small">
                    A execução pausa em 2.2.1 para você enviar o material de elicitação (transcrições de entrevistas,
                    atas de workshops…). {elicitationDocs > 0 ? `${elicitationDocs} documento(s) já enviados.` : "Você pode enviá-lo agora, na aba de fontes, ou quando a plataforma pedir."}
                  </div>
                </>
              )}
              {!hasScope && <div className="alert warn">Envie o documento de escopo antes de iniciar.</div>}
              {!ready && <div className="alert info">Sem base de referência indexada: os requisitos complementares não terão evidências.</div>}
              <label>Estratégia de contexto
                <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                  {STRATEGIES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </label>
              <label>Agentes
                <select value={gateway} onChange={(e) => setGateway(e.target.value)}>
                  <option value="baml">LLM real (BAML)</option>
                  <option value="fake">Simulado (sem LLM, para testar o processo)</option>
                </select>
              </label>
              <ErrorBox error={start.error} />
              <button className="primary" disabled={!hasScope || start.isPending || (phase !== "1" && !baseRun)}>Iniciar</button>
            </form>
          )}
        </div>
      )}

      {tab === "fontes" && (
        <div className="split">
          <div className="stack">
            <div className="card">
              <h2>Documentos</h2>
              <table>
                <thead><tr><th>Arquivo</th><th>Tipo</th><th>Páginas</th><th></th></tr></thead>
                <tbody>
                  {p.fontes.map((f) => (
                    <tr key={f.id} style={{ opacity: f.ativo ? 1 : 0.5 }}>
                      <td>{f.arquivo}</td><td><span className="badge">{f.source_kind}</span></td>
                      <td>{f.paginas ?? "—"}{Number(f.meta?.paginas_vazias ?? 0) > 0 &&
                        <span className="badge warn" title="páginas sem texto extraível">{String(f.meta.paginas_vazias)} vazias</span>}</td>
                      <td>{isEngineer && f.ativo && <button className="danger" onClick={() => deactivate.mutate(f.id)}>Desativar</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h2>Versões do corpus</h2>
              <table>
                <thead><tr><th>Criada</th><th>Status</th><th>Embedding</th><th>Chunks</th><th>Reaproveitados</th></tr></thead>
                <tbody>
                  {p.corpora.map((c) => (
                    <tr key={c.id}>
                      <td>{fmtDate(c.created_at)}</td><td><Status value={c.status} /></td>
                      <td className="small">{c.embedding_provider} · {c.embedding_model}</td>
                      <td>{c.stats?.chunks ?? "—"}</td><td>{c.stats?.embeddings_reaproveitados ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {isEngineer && (
            <div className="card stack">
              <h2>Enviar documentos</h2>
              <label>Tipo<select value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
              </select></label>
              <input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => setFiles(e.target.files)} />
              <ErrorBox error={upload.error} />
              <button className="primary" disabled={!files?.length || upload.isPending} onClick={() => upload.mutate()}>Enviar</button>
              <hr style={{ border: 0, borderTop: "1px solid var(--border)", width: "100%" }} />
              <div className="muted small">Indexar gera uma nova versão da base de referência (chunking estrutural e embeddings), reaproveitando trechos inalterados. O material de elicitação é indexado pela própria execução, em 2.2.1.</div>
              <ErrorBox error={index.error} />
              <button onClick={() => index.mutate()} disabled={index.isPending}>Indexar base de referência</button>
            </div>
          )}
        </div>
      )}

      {tab === "membros" && <Members project={p} canEdit={isEngineer} onChange={refresh} />}
    </div>
  );
}

function Members({ project, canEdit, onChange }: { project: ProjectDetail; canEdit: boolean; onChange: () => void }) {
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/users"), enabled: canEdit });
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("participant");
  const [theory, setTheory] = useState("");
  const add = useMutation({
    mutationFn: () => api.post(`/projects/${project.id}/members`,
      { user_id: userId, papel_plataforma: role, papel_openupexp: theory || null }),
    onSuccess: onChange,
  });
  return (
    <div className="split">
      <div className="card">
        <table>
          <thead><tr><th>Pessoa</th><th>Papel na plataforma</th><th>Papel OpenUPExp</th></tr></thead>
          <tbody>
            {project.membros.map((m) => (
              <tr key={m.user.id}><td>{m.user.nome} <span className="muted small">{m.user.email}</span></td>
                <td>{m.papel_plataforma}</td><td>{m.papel_openupexp ?? "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {canEdit && (
        <form className="card stack" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <h2>Adicionar membro</h2>
          <label>Pessoa<select value={userId} onChange={(e) => setUserId(e.target.value)} required>
            <option value="">—</option>
            {users.data?.map((u) => <option key={u.id} value={u.id}>{u.nome} ({u.email})</option>)}
          </select></label>
          <label>Papel na plataforma<select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="requirements_engineer">Engenheiro(a) de Requisitos — decide gateways</option>
            <option value="participant">Participante — consensos</option>
            <option value="observer">Observador — leitura</option>
            <option value="researcher">Pesquisador — experimentos</option>
          </select></label>
          <label>Papel teórico (OpenUPExp)<input value={theory} onChange={(e) => setTheory(e.target.value)}
            placeholder="ex.: Especialista em Regulação" /></label>
          <ErrorBox error={add.error} />
          <button className="primary" disabled={!userId}>Adicionar</button>
        </form>
      )}
    </div>
  );
}
