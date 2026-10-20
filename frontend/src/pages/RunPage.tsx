import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, downloadUrl } from "../api/client";
import type { ArtifactSummary, Manifest, Metrics, RunDetail, TaskExec, TaskSpec } from "../api/types";
import { taskName } from "../bpmn/names";
import BpmnNavigator from "../components/BpmnNavigator";
import Icon from "../components/Icon";
import TaskPanel from "../components/TaskPanel";
import { Empty, ErrorBox, Loading, MECHANISM, Markdown, PHASES, PhaseIcon, Status, Tabs, fmtDate } from "../components/ui";
import { useRunEvents } from "../hooks";

type Tab = "andamento" | "documento" | "resultados" | "uso";

export function taskSpecs(manifest: Manifest): Map<string, TaskSpec> {
  return new Map(manifest.phases.flatMap((p) => p.subprocesses.flatMap((s) => s.tasks)).map((t) => [t.id, t]));
}

function pendingKind(taskId: string | null): "input" | "approval" | "consensus" {
  if (taskId?.endsWith(".in")) return "input";
  if (taskId?.endsWith(".gate")) return "approval";
  return "consensus";
}

const PENDING_TEXT = {
  input: { title: "Agora é com você: envie o material das conversas",
    text: "Converse com as pessoas seguindo o roteiro sugerido pela IA e envie as transcrições ou anotações.", action: "Enviar material" },
  approval: { title: "Agora é com você: revise e aprove",
    text: "A IA terminou esta etapa. Leia o resultado e aprove, ou peça para a IA refazer alguma parte.", action: "Revisar e decidir" },
  consensus: { title: "A equipe precisa dar a opinião",
    text: "Cada pessoa diz se concorda com o resultado. Depois, o responsável encerra ou pede ajustes.", action: "Abrir a rodada" },
};

export default function RunPage() {
  const { runId = "" } = useParams();
  const [tab, setTab] = useState<Tab | null>(null);
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

  if (run.isLoading || manifest.isLoading) return <Loading what="Carregando a execução" />;
  if (!run.data || !manifest.data) return <ErrorBox error={run.error ?? manifest.error} />;
  const r = run.data;
  const info = PHASES[r.phase];
  const specs = taskSpecs(manifest.data);
  const current = r.current_task ? specs.get(r.current_task.replace(/\.in$/, "")) : undefined;
  const activeTab: Tab = tab ?? (r.status === "completed" ? "documento" : "andamento");
  const pending = PENDING_TEXT[pendingKind(r.current_task)];

  return (
    <div className="stack">
      <div>
        <Link to={`/projetos/${r.project_id}`} className="back"><Icon name="arrowLeft" size={14} />Voltar ao projeto</Link>
        <div className="page-head">
          <PhaseIcon phase={r.phase} size={26} />
          <div className="grow">
            <h1>Etapa {r.phase}: {info?.titulo ?? ""}</h1>
            <div className="subtitle">
              {info?.nome} · iniciada em {fmtDate(r.created_at)} · {r.agent_gateway === "fake" ? "modo de teste (sem IA)" : "com IA"}
              {r.base_run_id && <> · a partir do <Link to={`/execucoes/${r.base_run_id}`}>resultado aprovado da etapa {Number(r.phase) - 1}</Link></>}
            </div>
          </div>
        </div>
      </div>

      {r.pending_hitl ? (
        <div className="banner waiting">
          <span className="banner-icon"><Icon name="bell" size={24} /></span>
          <div className="grow"><div className="banner-title">{pending.title}</div><div className="muted">{pending.text}</div></div>
          <Link to={`/decisoes/${r.pending_hitl}`} className="btn primary big">{pending.action}<Icon name="arrowRight" /></Link>
        </div>
      ) : r.status === "completed" ? (
        <div className="banner done">
          <span className="banner-icon"><Icon name="checkCircle" size={24} /></span>
          <div className="grow"><div className="banner-title">Etapa concluída e aprovada</div>
            <div className="muted">O resultado já faz parte do documento do projeto.{r.phase !== "4" && " Você pode seguir para a próxima etapa na página do projeto."}</div></div>
          <Link to={`/projetos/${r.project_id}`} className="btn">{r.phase !== "4" ? "Ir para a próxima etapa" : "Voltar ao projeto"}<Icon name="arrowRight" /></Link>
        </div>
      ) : r.status === "failed" ? (
        <div className="banner failed">
          <span className="banner-icon"><Icon name="xCircle" size={24} /></span>
          <div className="grow"><div className="banner-title">A execução parou com um erro</div>
            <div className="muted">Nada se perdeu: dá para continuar do último ponto salvo.</div></div>
          <button className="primary" onClick={() => retry.mutate()} disabled={retry.isPending}><Icon name="redo" />Tentar de novo</button>
        </div>
      ) : (
        <div className="banner running">
          <span className="banner-icon"><span className="spinner" /></span>
          <div className="grow"><div className="banner-title">A IA está trabalhando…</div>
            <div className="muted">{current ? <>Agora: <strong>{taskName(current.id, current.name)}</strong> ({MECHANISM[current.mechanism]?.label ?? current.mechanism})</> : "Preparando."}
              {" "}A página se atualiza sozinha.</div></div>
        </div>
      )}
      {r.error && <details className="alert err"><summary>Detalhes do erro</summary><pre>{r.error}</pre></details>}
      <ErrorBox error={retry.error} />

      <Tabs value={activeTab} onChange={setTab} items={[
        { id: "andamento", label: "Andamento", icon: "map" },
        { id: "documento", label: r.phase === "1" ? "Documento de Visão" : "Documento", icon: "file" },
        { id: "resultados", label: "Resultados por parte", icon: "layers" },
        { id: "uso", label: "Uso da IA", icon: "chart" },
      ]} />

      {activeTab === "andamento" && (
        <div className="split">
          <div className="card stack">
            <div className="card-head"><span className="icon-bubble"><Icon name="map" /></span>
              <span className="grow"><h2>Mapa do processo</h2><div className="muted small">Clique em um bloco para ver os detalhes.</div></span></div>
            <BpmnNavigator manifest={manifest.data} tasks={tasks.data ?? []} selected={selected} onSelect={setSelected} />
          </div>
          {selected ? (
            <div className="stack">
              <button className="ghost" style={{ alignSelf: "flex-start" }} onClick={() => setSelected(null)}><Icon name="arrowLeft" size={14} />Passo a passo</button>
              <TaskPanel elementId={selected} manifest={manifest.data} tasks={tasks.data ?? []} />
            </div>
          ) : <StepByStep tasks={tasks.data ?? []} specs={specs} onSelect={setSelected} lastEvent={lastEvent} />}
        </div>
      )}
      {activeTab === "documento" && <Document runId={runId} />}
      {activeTab === "resultados" && <Artifacts runId={runId} />}
      {activeTab === "uso" && <MetricsView runId={runId} r={r} />}
    </div>
  );
}

function StepByStep({ tasks, specs, onSelect, lastEvent }: {
  tasks: TaskExec[]; specs: Map<string, TaskSpec>; onSelect: (el: string) => void; lastEvent: string;
}) {
  return (
    <div className="card stack">
      <div className="card-head"><span className="icon-bubble"><Icon name="list" /></span><h2 className="grow">Passo a passo</h2></div>
      {tasks.length === 0 && <Loading what="Aguardando o início" />}
      <div className="steps-list">
        {tasks.map((t) => {
          const spec = specs.get(t.task_id.replace(/\.in$/, ""));
          const mech = t.task_id.endsWith(".in") ? "hitl_approval" : spec?.mechanism ?? "deterministic";
          const m = MECHANISM[mech];
          return (
            <div key={t.id} className="list-item" onClick={() => t.bpmn_element_id && onSelect(t.bpmn_element_id)}>
              <span className={`mech ${mech}`} title={m?.label}><Icon name={m?.icon ?? "zap"} size={15} /></span>
              <span className="grow">
                <div className="small strong">{taskName(t.task_id, spec?.name)}</div>
                <div className="tiny muted">{t.task_id}{t.iteracao > 1 ? ` · ${t.iteracao}ª vez` : ""} · {fmtDate(t.inicio)}</div>
              </span>
              <Status value={t.status} />
            </div>
          );
        })}
      </div>
      {lastEvent && <div className="tiny muted">Última atualização: {lastEvent}</div>}
    </div>
  );
}

function Artifacts({ runId }: { runId: string }) {
  const arts = useQuery({ queryKey: ["artifacts", runId], queryFn: () => api.get<ArtifactSummary[]>(`/runs/${runId}/artifacts`) });
  if (arts.isLoading) return <Loading />;
  const visible = (arts.data ?? []).filter((a) => !a.artifact_type.startsWith("digest."));
  return (
    <div className="cards">
      {visible.map((a) => (
        <Link key={a.id} to={`/versoes/${a.id}`} className="tile">
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <span className="icon-bubble"><Icon name={a.secao ? "layers" : "file"} size={18} /></span>
            <span className="grow strong">{a.title}</span>
          </div>
          <div className="row small">
            <Status value={a.status} />{a.origin === "human_edit" && <Status value="human_edit" />}
            <span className="muted">{a.itens != null ? `${a.itens} itens · ` : ""}versão {a.version_no}</span>
          </div>
        </Link>
      ))}
      {visible.length === 0 && <div className="card"><Empty icon="layers">Ainda não há resultados.</Empty></div>}
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
      <div className="card">{doc.data ? <Markdown>{doc.data}</Markdown> : <Loading what="Montando o documento" />}</div>
      <div className="card stack">
        <div className="card-head"><span className="icon-bubble"><Icon name="download" /></span><h2>Baixar</h2></div>
        <div className="muted small">O documento final é gerado quando a etapa é aprovada. Ao lado, você vê a versão atual.</div>
        {exports.data?.map((e) => (
          <a key={e.id} href={downloadUrl(e.id)} className="btn"><Icon name="download" />Documento de {fmtDate(e.created_at)} (.md)</a>
        ))}
        {exports.data?.length === 0 && <Empty icon="file">Disponível depois da aprovação.</Empty>}
      </div>
    </div>
  );
}

function MetricsView({ runId, r }: { runId: string; r: RunDetail }) {
  const m = useQuery({ queryKey: ["run", runId, "metrics"], queryFn: () => api.get<Metrics>(`/runs/${runId}/metrics`) });
  if (!m.data) return <Loading />;
  const max = Math.max(1, ...m.data.por_tarefa.map((t) => t.input_tokens + t.output_tokens));
  const t = m.data.total;
  return (
    <div className="card stack">
      {r.agent_gateway === "fake" && <div className="alert info"><Icon name="info" />Modo de teste: não houve uso real de IA.</div>}
      <div className="row">
        <div className="stat"><span className="value">{t.llm_calls}</span><span className="label">chamadas à IA</span></div>
        <div className="stat"><span className="value">{(t.input_tokens + t.output_tokens).toLocaleString("pt-BR")}</span><span className="label">tokens (texto lido + escrito)</span></div>
        <div className="stat"><span className="value">{(t.latency_ms / 1000).toFixed(1)} s</span><span className="label">tempo de resposta somado</span></div>
        <div className="stat"><span className="value">{t.custo_usd != null ? `US$ ${t.custo_usd.toFixed(4)}` : "—"}</span><span className="label">custo estimado</span></div>
      </div>
      <table className="small">
        <thead><tr><th>Tarefa</th><th>Vez</th><th>Função</th><th style={{ width: "40%" }}>Tokens</th><th>Tempo</th></tr></thead>
        <tbody>
          {m.data.por_tarefa.map((x, i) => {
            const total = x.input_tokens + x.output_tokens;
            return (
              <tr key={i}>
                <td className="mono">{x.task_id}</td><td>{x.iteracao}</td><td className="mono">{x.function}</td>
                <td><div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                  <div className="meter" style={{ width: `${(total / max) * 100}%` }} /><span>{total.toLocaleString("pt-BR")}</span></div></td>
                <td>{x.latency_ms} ms</td>
              </tr>
            );
          })}
          {m.data.por_tarefa.length === 0 && <tr><td colSpan={5}><Empty icon="chart">Sem chamadas registradas.</Empty></td></tr>}
        </tbody>
      </table>
    </div>
  );
}
