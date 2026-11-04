import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Manifest, PackageItem, TaskDetail, TaskExec } from "../api/types";
import { taskByElement } from "../bpmn/status";
import { taskName } from "../bpmn/names";
import Icon from "./Icon";
import { ErrorBox, Loading, MECHANISM, Status, fmtDate, show } from "./ui";

const ORIGIN_LABEL: Record<string, string> = {
  required: "resultado anterior", previous: "versão anterior", digest: "resumo de etapa", retrieved: "trecho de documento",
  related: "relacionado", feedback: "comentário humano", document: "documento inteiro",
};

export default function TaskPanel({ elementId, manifest, tasks }: {
  elementId: string; manifest: Manifest; tasks: TaskExec[];
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
        <div className="card-head">
          {spec && <span className={`mech ${spec.mechanism}`}><Icon name={MECHANISM[spec.mechanism]?.icon ?? "zap"} size={16} /></span>}
          <span className="grow"><h2>{spec ? taskName(spec.id, spec.name) : elementId}</h2>
            {spec && <div className="muted small">{spec.id} · no processo: <em>{spec.name}</em> · feita por: {MECHANISM[spec.mechanism]?.label ?? spec.mechanism}</div>}</span>
        </div>
        {spec && (
          <details className="advanced">
            <summary>Detalhes técnicos</summary>
            <dl className="kv small">
              {spec.baml_function && <><dt>Função</dt><dd className="mono">{spec.baml_function}</dd></>}
              <dt>Lê</dt><dd>{spec.reads.map((r) => `${r.artifact}${r.required ? "" : " (opcional)"}`).join(", ") || "—"}</dd>
              <dt>Produz</dt><dd>{spec.writes.map((w) => w.artifact).join(", ") || "—"}</dd>
              {spec.theory_ref && <><dt>Teoria</dt><dd>{spec.theory_ref}</dd></>}
              {spec.pending.length > 0 && <><dt>Pendências</dt><dd>{spec.pending.map((p) => <span key={p} className="badge warn">{p}</span>)}</dd></>}
            </dl>
          </details>
        )}
        {anchored.length > 0 && (
          <div className="alert info small" style={{ marginTop: 8 }}>
            Também acontece neste bloco: {anchored.map((a) => `${a.id} ${taskName(a.id, a.name)}`).join(", ")}
          </div>
        )}
      </div>
      {executions.length === 0 ? <div className="muted">Esta parte ainda não foi feita.</div> : (
        <>
          <div className="timeline">
            {executions.map((t) => (
              <button key={t.id} className={t.id === current?.id ? "primary" : ""} onClick={() => setChosen(t.id)}>
                {t.iteracao}ª vez
              </button>
            ))}
          </div>
          {current && <ExecutionDetail exec={current} />}
        </>
      )}
    </div>
  );
}

function ExecutionDetail({ exec }: { exec: TaskExec }) {
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
      {hitl && <Link to={`/decisoes/${hitl}`}>Abrir a decisão →</Link>}
      {exec.status === "completed" && d.context_package && d.llm_calls.length > 0 && (
        <Link to={`/laboratorio?tarefa=${exec.id}`} className="btn small" style={{ alignSelf: "flex-start" }}>
          <Icon name="chart" size={14} />Comparar modelos nesta tarefa</Link>
      )}
      {versions.length > 0 && (
        <div className="row small">Resultados gerados: {versions.map((v) => <Link key={v} to={`/versoes/${v}`} className="mono">{v.slice(0, 8)}</Link>)}</div>
      )}
      {pkg && (
        <details open>
          <summary><strong>O que a IA recebeu para ler</strong> · ~{pkg.token_estimate.toLocaleString("pt-BR")} tokens ·{" "}
            {pkg.coverage.satisfied ? <span className="badge ok">nada faltou</span>
              : <span className="badge err">faltou {pkg.coverage.missing_ids.join(", ")}</span>}
          </summary>
          <div className="stack" style={{ marginTop: 8 }}>
            {pkg.items.map((it, i) => <ContextItemView key={i} item={it} />)}
          </div>
        </details>
      )}
      {d.llm_calls.length > 0 && (
        <details>
          <summary><strong>Chamadas à IA</strong> ({d.llm_calls.length})</summary>
          <table className="small">
            <thead><tr><th>Função</th><th>Modelo</th><th>Tokens (lidos/escritos)</th><th>Tempo</th><th>Situação</th></tr></thead>
            <tbody>
              {d.llm_calls.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.function}</td>
                  <td>{c.provider}/{c.model ?? c.client}{c.fallback_chain.length > 1 && <span className="badge warn">modelo reserva ×{c.fallback_chain.length}</span>}</td>
                  <td>{show(c.input_tokens)} / {show(c.output_tokens)}</td>
                  <td>{c.latency_ms ?? "—"} ms</td>
                  <td><span className={`badge ${c.status === "ok" ? "ok" : "err"}`}>{c.status}</span>{c.error && <div className="small">{c.error}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
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
        <span className="muted small">{text.length.toLocaleString("pt-BR")} caracteres</span>
      </summary>
      <pre style={{ maxHeight: 280, overflow: "auto", marginTop: 6 }}>{text}</pre>
    </details>
  );
}
