import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Manifest, PackageItem, TaskDetail, TaskExec } from "../api/types";
import { taskByElement } from "../bpmn/status";
import { ErrorBox, Loading, Status, fmtDate, show } from "./ui";

const ORIGIN_LABEL: Record<string, string> = {
  required: "entrada declarada", previous: "versão anterior", digest: "digest", retrieved: "recuperado (RAG)",
  related: "relacionado", feedback: "feedback humano", document: "documento integral",
};

export default function TaskPanel({ elementId, manifest, tasks, runId }: {
  elementId: string; manifest: Manifest; tasks: TaskExec[]; runId: string;
}) {
  const spec = taskByElement(elementId, manifest);
  const executions = tasks.filter((t) => t.bpmn_element_id === elementId);
  const [chosen, setChosen] = useState<string | null>(null);
  const current = executions.find((t) => t.id === chosen) ?? executions[executions.length - 1];
  const anchored = manifest.phases.flatMap((p) => p.subprocesses.flatMap((s) => s.tasks))
    .filter((t) => t.bpmn_anchor === elementId && !t.bpmn_element);

  return (
    <div className="card stack">
      <div>
        <h2>{spec ? `${spec.id} ${spec.name}` : elementId}</h2>
        {spec && (
          <dl className="kv">
            <dt>Mecanismo</dt><dd>{spec.mechanism}{spec.baml_function && <span className="mono"> · {spec.baml_function}</span>}</dd>
            <dt>Entradas</dt><dd>{spec.reads.map((r) => `${r.artifact}${r.required ? "" : " (opcional)"}`).join(", ") || "—"}</dd>
            <dt>Saídas</dt><dd>{spec.writes.map((w) => w.artifact).join(", ") || "—"}</dd>
            {spec.theory_ref && <><dt>Teoria</dt><dd className="small">{spec.theory_ref}</dd></>}
            {spec.pending.length > 0 && <><dt>Pendências</dt><dd>{spec.pending.map((p) => <span key={p} className="badge warn">{p}</span>)}</dd></>}
          </dl>
        )}
        {anchored.length > 0 && (
          <div className="alert info small" style={{ marginTop: 8 }}>
            Também ancorada aqui (sem tarefa BPMN própria): {anchored.map((a) => `${a.id} ${a.name}`).join(", ")}
          </div>
        )}
      </div>
      {executions.length === 0 ? <div className="muted">Ainda não executada nesta execução.</div> : (
        <>
          <div className="timeline">
            {executions.map((t) => (
              <button key={t.id} className={t.id === current?.id ? "primary" : ""} onClick={() => setChosen(t.id)}>
                {t.task_id} · it{t.iteracao}
              </button>
            ))}
          </div>
          {current && <ExecutionDetail exec={current} runId={runId} />}
        </>
      )}
    </div>
  );
}

function ExecutionDetail({ exec, runId }: { exec: TaskExec; runId: string }) {
  const detail = useQuery({ queryKey: ["task", exec.id, exec.status], queryFn: () => api.get<TaskDetail>(`/task-executions/${exec.id}`) });
  if (detail.isLoading) return <Loading />;
  if (!detail.data) return <ErrorBox error={detail.error} />;
  const d = detail.data;
  const pkg = d.context_package;
  const versions = (d.meta?.versions as string[] | undefined) ?? [];
  const hitl = d.meta?.hitl_request_id as string | undefined;
  return (
    <div className="stack">
      <div className="row"><Status value={exec.status} /><span className="muted small">{fmtDate(exec.inicio)} → {fmtDate(exec.fim)}</span></div>
      {d.erro && <div className="alert err small"><pre>{d.erro}</pre></div>}
      {hitl && <Link to={`/decisoes/${hitl}`}>Abrir decisão humana →</Link>}
      {versions.length > 0 && (
        <div className="row small">Versões produzidas: {versions.map((v) => <Link key={v} to={`/versoes/${v}`} className="mono">{v.slice(0, 8)}</Link>)}</div>
      )}
      {pkg && (
        <details open>
          <summary><strong>Contexto entregue ao agente</strong> · {pkg.strategy} · ~{pkg.token_estimate} tokens ·{" "}
            {pkg.coverage.satisfied ? <span className="badge ok">cobertura completa</span>
              : <span className="badge err">faltando {pkg.coverage.missing_ids.join(", ")}</span>}
          </summary>
          <div className="stack" style={{ marginTop: 8 }}>
            {pkg.items.map((it, i) => <ContextItemView key={i} item={it} />)}
          </div>
        </details>
      )}
      {d.llm_calls.length > 0 && (
        <details>
          <summary><strong>Chamadas LLM</strong> ({d.llm_calls.length})</summary>
          <table className="small">
            <thead><tr><th>Função</th><th>Modelo</th><th>Tokens (in/out)</th><th>Latência</th><th>Status</th></tr></thead>
            <tbody>
              {d.llm_calls.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.function}</td>
                  <td>{c.provider}/{c.model ?? c.client}{c.fallback_chain.length > 1 && <span className="badge warn">fallback ×{c.fallback_chain.length}</span>}</td>
                  <td>{show(c.input_tokens)} / {show(c.output_tokens)}</td>
                  <td>{c.latency_ms ?? "—"} ms</td>
                  <td><span className={`badge ${c.status === "ok" ? "ok" : "err"}`}>{c.status}</span>{c.error && <div className="small">{c.error}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      <Link to={`/execucoes/${runId}`} className="small muted">{exec.id}</Link>
    </div>
  );
}

function ContextItemView({ item }: { item: PackageItem }) {
  const text = typeof item.content === "string" ? item.content : JSON.stringify(item.content, null, 1);
  return (
    <details className="item-card">
      <summary className="row" style={{ gap: 8 }}>
        <span className={`badge ${item.origin === "feedback" ? "waiting_human" : item.origin === "retrieved" ? "running" : ""}`}>
          {ORIGIN_LABEL[item.origin] ?? item.origin}</span>
        <span className="mono small">{item.artifact ?? item.ref}</span>
        <span className="muted small grow">{item.reason}</span>
        <span className="muted small">{text.length} car.</span>
      </summary>
      <pre style={{ maxHeight: 280, overflow: "auto", marginTop: 6 }}>{text}</pre>
    </details>
  );
}
