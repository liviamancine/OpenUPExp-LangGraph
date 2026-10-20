import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, downloadUrl } from "../api/client";
import type { ArtifactSummary, Manifest, Metrics, RunDetail, TaskExec } from "../api/types";
import BpmnNavigator from "../components/BpmnNavigator";
import TaskPanel from "../components/TaskPanel";
import { ErrorBox, Loading, Markdown, PHASE_NAMES, Status, Tabs, fmtDate } from "../components/ui";
import { useRunEvents } from "../hooks";

type Tab = "processo" | "artefatos" | "documento" | "metricas";

export default function RunPage() {
  const { runId = "" } = useParams();
  const [tab, setTab] = useState<Tab>("processo");
  const [selected, setSelected] = useState<string | null>(null);
  const [lastEvent, setLastEvent] = useState<string>("");
  const onEvent = useCallback((tipo: string, dados: Record<string, unknown>) => {
    setLastEvent(`${tipo}${dados.task_id ? ` · ${dados.task_id}` : ""}`);
  }, []);
  useRunEvents(runId, onEvent);

  const run = useQuery({ queryKey: ["run", runId], queryFn: () => api.get<RunDetail>(`/runs/${runId}`) });
  const tasks = useQuery({ queryKey: ["tasks", runId], queryFn: () => api.get<TaskExec[]>(`/runs/${runId}/tasks`) });
  const manifest = useQuery({ queryKey: ["manifest"], queryFn: () => api.get<Manifest>("/process/manifest"), staleTime: Infinity });
  const retry = useMutation({ mutationFn: () => api.post(`/runs/${runId}/retry`), onSuccess: () => run.refetch() });

  if (run.isLoading || manifest.isLoading) return <Loading />;
  if (!run.data || !manifest.data) return <ErrorBox error={run.error ?? manifest.error} />;
  const r = run.data;

  return (
    <div className="stack">
      <div className="row">
        <div className="grow">
          <div className="small"><Link to={`/projetos/${r.project_id}`}>← projeto</Link></div>
          <h1>Fase {r.phase} — {PHASE_NAMES[r.phase] ?? ""} · execução <span className="mono">{r.id.slice(0, 8)}</span></h1>
          {r.base_run_id && <div className="small muted">Execução de base: <Link to={`/execucoes/${r.base_run_id}`} className="mono">{r.base_run_id.slice(0, 8)}</Link></div>}
          <div className="row small muted">
            <Status value={r.status} />
            {r.current_task && <span>tarefa atual: {r.current_task}</span>}
            <span>estratégia {r.context_strategy}</span>
            <span>agentes: {r.agent_gateway === "fake" ? "simulados" : "LLM (BAML)"}</span>
            <span>manifesto {r.manifest_version}</span>
            <span>{r.metricas.llm_calls} chamadas · {(r.metricas.input_tokens + r.metricas.output_tokens).toLocaleString("pt-BR")} tokens</span>
            {lastEvent && <span>último evento: {lastEvent}</span>}
          </div>
        </div>
        {r.pending_hitl && <Link to={`/decisoes/${r.pending_hitl}`}><button className="primary">{r.current_task?.endsWith(".in") ? "Enviar material" : "Revisar e decidir"}</button></Link>}
        {r.status === "failed" && <button onClick={() => retry.mutate()} disabled={retry.isPending}>Retomar do último checkpoint</button>}
      </div>
      {r.error && <div className="alert err"><pre>{r.error}</pre></div>}
      <ErrorBox error={retry.error} />

      <Tabs value={tab} onChange={setTab} items={[
        { id: "processo", label: "Processo" }, { id: "artefatos", label: "Artefatos" },
        { id: "documento", label: r.phase === "1" ? "Documento de Visão" : "Documento (ERD)" }, { id: "metricas", label: "Métricas" },
      ]} />

      {tab === "processo" && (
        <div className="split">
          <div className="card">
            <BpmnNavigator manifest={manifest.data} tasks={tasks.data ?? []} selected={selected} onSelect={setSelected} />
          </div>
          {selected ? <TaskPanel elementId={selected} manifest={manifest.data} tasks={tasks.data ?? []} runId={runId} />
            : <Timeline tasks={tasks.data ?? []} onSelect={setSelected} />}
        </div>
      )}
      {tab === "artefatos" && <Artifacts runId={runId} />}
      {tab === "documento" && <Document runId={runId} />}
      {tab === "metricas" && <MetricsView runId={runId} />}
    </div>
  );
}

function Timeline({ tasks, onSelect }: { tasks: TaskExec[]; onSelect: (el: string) => void }) {
  return (
    <div className="card stack">
      <h2>Linha do tempo</h2>
      {tasks.length === 0 && <div className="muted">Aguardando o worker…</div>}
      <table className="small">
        <tbody>
          {tasks.map((t) => (
            <tr key={t.id} className="list-item" onClick={() => t.bpmn_element_id && onSelect(t.bpmn_element_id)}>
              <td className="mono">{t.task_id}</td><td>it{t.iteracao}</td><td><Status value={t.status} /></td>
              <td className="muted">{fmtDate(t.inicio)}</td><td className="muted">{t.tokens ? `${t.tokens} tok` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Artifacts({ runId }: { runId: string }) {
  const arts = useQuery({ queryKey: ["artifacts", runId], queryFn: () => api.get<ArtifactSummary[]>(`/runs/${runId}/artifacts`) });
  if (arts.isLoading) return <Loading />;
  return (
    <div className="card">
      <table>
        <thead><tr><th>Artefato</th><th>Tipo</th><th>Versão</th><th>Itens</th><th>Status</th><th>Origem</th><th>Iteração</th></tr></thead>
        <tbody>
          {arts.data?.map((a) => (
            <tr key={a.id}>
              <td><Link to={`/versoes/${a.id}`}>{a.title}</Link></td>
              <td className="mono small">{a.artifact_type}</td><td>v{a.version_no}</td><td>{a.itens ?? "—"}</td>
              <td><Status value={a.status} /></td><td><Status value={a.origin} /></td><td>{a.iteracao}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ErrorBox error={arts.error} />
    </div>
  );
}

function Document({ runId }: { runId: string }) {
  const doc = useQuery({ queryKey: ["artifacts", runId, "doc"], queryFn: () => api.get<string>(`/runs/${runId}/document`) });
  const exports = useQuery({ queryKey: ["artifacts", runId, "exports"],
    queryFn: () => api.get<{ id: string; created_at: string; sha256: string }[]>(`/runs/${runId}/exports`) });
  return (
    <div className="split">
      <div className="card">{doc.data ? <Markdown>{doc.data}</Markdown> : <Loading />}</div>
      <div className="card stack">
        <h2>Exportações versionadas</h2>
        <div className="muted small">Geradas na consolidação da fase a partir dos artefatos aprovados. A prévia ao lado reflete as versões atuais.</div>
        {exports.data?.map((e) => (
          <a key={e.id} href={downloadUrl(e.id)}>{fmtDate(e.created_at)} · <span className="mono">{e.sha256.slice(0, 10)}</span>.md</a>
        ))}
        {exports.data?.length === 0 && <div className="muted">Nenhuma ainda.</div>}
      </div>
    </div>
  );
}

function MetricsView({ runId }: { runId: string }) {
  const m = useQuery({ queryKey: ["run", runId, "metrics"], queryFn: () => api.get<Metrics>(`/runs/${runId}/metrics`) });
  if (!m.data) return <Loading />;
  const max = Math.max(1, ...m.data.por_tarefa.map((t) => t.input_tokens + t.output_tokens));
  return (
    <div className="card stack">
      <div className="row">
        <span>Chamadas: <strong>{m.data.total.llm_calls}</strong></span>
        <span>Tokens entrada: <strong>{m.data.total.input_tokens.toLocaleString("pt-BR")}</strong></span>
        <span>Tokens saída: <strong>{m.data.total.output_tokens.toLocaleString("pt-BR")}</strong></span>
        <span>Latência somada: <strong>{(m.data.total.latency_ms / 1000).toFixed(1)} s</strong></span>
        <span>Custo: <strong>{m.data.total.custo_usd != null ? `US$ ${m.data.total.custo_usd.toFixed(4)}` : "sem tabela de preços"}</strong></span>
      </div>
      <table className="small">
        <thead><tr><th>Tarefa</th><th>It.</th><th>Função</th><th style={{ width: "40%" }}>Tokens</th><th>Latência</th></tr></thead>
        <tbody>
          {m.data.por_tarefa.map((t, i) => {
            const total = t.input_tokens + t.output_tokens;
            return (
              <tr key={i}>
                <td className="mono">{t.task_id}</td><td>{t.iteracao}</td><td className="mono">{t.function}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ height: 8, width: `${(total / max) * 100}%`, background: "var(--accent)", borderRadius: 4, minWidth: 2 }} />
                    <span>{total.toLocaleString("pt-BR")}</span>
                  </div>
                </td>
                <td>{t.latency_ms} ms</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
