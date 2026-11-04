import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LabSource, LabSummary, LlmProfile, Project, ProjectDetail } from "../api/types";
import { taskName } from "../bpmn/names";
import Icon from "../components/Icon";
import { Empty, ErrorBox, Loading, PhaseChip, fmtDate } from "../components/ui";

export const STRATEGY_OPTIONS = [
  { id: "original", label: "Como foi executada", help: "O mesmo material que a tarefa recebeu." },
  { id: "C", label: "C · Só as entradas", help: "Apenas os resultados anteriores declarados." },
  { id: "D", label: "D · Equilibrada", help: "Entradas + resumos das etapas anteriores." },
  { id: "A", label: "A · Tudo", help: "Entradas + documento inteiro (versão atual)." },
  { id: "B", label: "B · Por semelhança", help: "Só os itens mais parecidos com a tarefa (top-8)." },
];
export const STRATEGY_LABEL: Record<string, string> = Object.fromEntries(STRATEGY_OPTIONS.map((x) => [x.id, x.label]));

const RUN_STATUS: Record<string, string> = {
  completed: "concluída", running: "em andamento", queued: "na fila", waiting_human: "aguardando decisão", failed: "com erro",
};

export default function LabPage() {
  const [params] = useSearchParams();
  const [creating, setCreating] = useState(!!params.get("tarefa"));
  const list = useQuery({ queryKey: ["lab"], queryFn: () => api.get<LabSummary[]>("/lab/comparisons") });

  return (
    <div className="stack">
      <section className="hero">
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow">
            <h1>Laboratório de modelos</h1>
            <div className="subtitle">Escolha uma tarefa já executada e refaça-a com outros modelos, usando exatamente
              o mesmo material de entrada. Assim, a diferença nos resultados vem do modelo — não do contexto.</div>
          </div>
          <button className="light big" onClick={() => setCreating(true)}><Icon name="plus" />Nova comparação</button>
        </div>
        <div className="hero-steps">
          <div className="hero-step"><span className="num"><Icon name="list" size={18} /></span>
            <span><div className="strong">1. Escolha a tarefa</div><div className="small muted">De qualquer execução concluída.</div></span></div>
          <div className="hero-step"><span className="num"><Icon name="sparkles" size={18} /></span>
            <span><div className="strong">2. Escolha os modelos</div><div className="small muted">Até 6, incluindo o local.</div></span></div>
          <div className="hero-step"><span className="num"><Icon name="chart" size={18} /></span>
            <span><div className="strong">3. Compare e avalie</div><div className="small muted">Métricas automáticas e sua nota.</div></span></div>
        </div>
      </section>

      {creating && <NewComparison initialTask={params.get("tarefa")} initialRun={params.get("execucao")} onCancel={() => setCreating(false)} />}

      {list.isLoading ? <Loading /> : (
        <div className="stack tight">
          {list.data?.map((c) => (
            <Link key={c.id} to={`/laboratorio/${c.id}`} className="task-row">
              <span className="kind-icon consensus"><Icon name="chart" size={20} /></span>
              <span className="grow">
                <div className="strong">{taskName(c.task_id, c.nome)} <span className="muted small">· {c.projeto}</span></div>
                <div className="row tiny muted" style={{ gap: 8, marginTop: 4 }}>
                  <PhaseChip phase={c.fase} /><span>{c.task_id}</span><span>· {fmtDate(c.created_at)}</span>
                </div>
                <div className="row small" style={{ gap: 6, marginTop: 6 }}>
                  {c.modelos.map((m, i) => <span key={i} className={`badge ${c.situacao[i]}`}>{m ?? "—"}</span>)}
                </div>
              </span>
              <span className="btn small">Abrir<Icon name="arrowRight" size={14} /></span>
            </Link>
          ))}
          {list.data?.length === 0 && !creating && <div className="card"><Empty icon="chart">Nenhuma comparação ainda.</Empty></div>}
        </div>
      )}
      <ErrorBox error={list.error} />
    </div>
  );
}

function NewComparison({ initialTask, initialRun, onCancel }: {
  initialTask: string | null; initialRun: string | null; onCancel: () => void;
}) {
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get<Project[]>("/projects") });
  const [projectId, setProjectId] = useState("");
  const project = useQuery({ queryKey: ["project", projectId], enabled: !!projectId,
    queryFn: () => api.get<ProjectDetail>(`/projects/${projectId}`) });
  const [runId, setRunId] = useState(initialRun ?? "");
  const sources = useQuery({ queryKey: ["lab-sources", runId], enabled: !!runId,
    queryFn: () => api.get<LabSource[]>(`/lab/sources/${runId}`) });
  const [taskExec, setTaskExec] = useState(initialTask ?? "");
  const profiles = useQuery({ queryKey: ["llm-profiles"], queryFn: () => api.get<LlmProfile[]>("/llm/profiles"),
    refetchOnWindowFocus: true });
  const [chosen, setChosen] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [strategies, setStrategies] = useState<string[]>(["original"]);
  const [reps, setReps] = useState(1);
  const total = chosen.length * strategies.length * reps;
  const create = useMutation({
    mutationFn: () => api.post<{ id: string }>("/lab/comparisons", {
      task_execution_id: taskExec, profiles: chosen, notes: notes || null, strategies, repeticoes: reps }),
    onSuccess: (r) => navigate(`/laboratorio/${r.id}`),
  });
  const toggle = (id: string) => setChosen((xs) => xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]);
  const toggleStrategy = (id: string) => setStrategies((xs) => xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]);

  return (
    <form className="card stack" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <div className="card-head"><span className="icon-bubble"><Icon name="plus" /></span><h2>Nova comparação</h2></div>
      {!initialTask && (
        <div className="grid-2">
          <label>Projeto<select value={projectId} onChange={(e) => { setProjectId(e.target.value); setRunId(""); setTaskExec(""); }} required>
            <option value="">Escolha…</option>
            {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
          </select></label>
          <label>Execução<select value={runId} onChange={(e) => { setRunId(e.target.value); setTaskExec(""); }} required disabled={!project.data}>
            <option value="">Escolha…</option>
            {project.data?.execucoes.map((r) => <option key={r.id} value={r.id}>Etapa {r.phase} · {fmtDate(r.created_at)} · {r.agent_gateway === "fake" ? "teste" : "IA"} · {RUN_STATUS[r.status] ?? r.status}</option>)}
          </select></label>
        </div>
      )}
      {runId && (
        <label>Tarefa
          <select value={taskExec} onChange={(e) => setTaskExec(e.target.value)} required>
            <option value="">Escolha…</option>
            {sources.data?.map((s) => <option key={s.task_execution_id} value={s.task_execution_id}>
              {s.task_id} · {taskName(s.task_id, s.nome)}{s.iteracao > 1 ? ` (${s.iteracao}ª vez)` : ""} · ~{s.tokens_contexto.toLocaleString("pt-BR")} tokens de contexto</option>)}
          </select>
          {sources.data?.length === 0 && <span className="muted small">Nenhuma tarefa da IA concluída nesta execução.</span>}
        </label>
      )}
      {initialTask && <div className="alert info small"><Icon name="info" />Tarefa escolhida a partir da execução.</div>}
      <div className="small muted">Modelos a comparar (até 6). A execução original entra sempre como referência.</div>
      <div className="choices">
        {profiles.data?.map((p) => (
          <label key={p.id} className={`choice ${chosen.includes(p.id) ? "selected" : ""}`} style={p.disponivel ? undefined : { opacity: 0.55 }}>
            <input type="checkbox" checked={chosen.includes(p.id)} disabled={!p.disponivel} onChange={() => toggle(p.id)} />
            <span><div className="title row" style={{ gap: 6 }}><Icon name={p.modelo.local ? "lock" : "sparkles"} size={15} />{p.nome}
              {p.modelo.local && <span className="badge ok">referência local</span>}</div>
              <div className="help">{p.disponivel ? `${p.modelo.provider} · ${p.modelo.model}` : p.modelo.local ? "Desligado nesta instalação." : "Sem chave configurada no servidor."}</div></span>
          </label>
        ))}
        <label className={`choice ${chosen.includes("fake") ? "selected" : ""}`}>
          <input type="checkbox" checked={chosen.includes("fake")} onChange={() => toggle("fake")} />
          <span><div className="title"><Icon name="zap" size={15} /> Modo de teste (simulado)</div><div className="help">Sem IA: útil para conhecer o laboratório.</div></span>
        </label>
      </div>
      <details className="advanced" open={strategies.length > 1 || reps > 1}>
        <summary>Experimento: estratégias de contexto e repetições</summary>
        <div className="stack tight">
          <div className="small muted">Além do modelo, você pode variar <strong>o quanto do material a IA recebe</strong>.
            Cada combinação modelo × estratégia vira uma coluna; as repetições mostram a variação entre execuções.</div>
          <div className="choices horizontal">
            {STRATEGY_OPTIONS.map((x) => (
              <label key={x.id} className={`choice ${strategies.includes(x.id) ? "selected" : ""}`}>
                <input type="checkbox" checked={strategies.includes(x.id)} onChange={() => toggleStrategy(x.id)} />
                <span><div className="title">{x.label}</div><div className="help">{x.help}</div></span>
              </label>
            ))}
          </div>
          <label style={{ maxWidth: 260 }}>Repetições de cada combinação
            <select value={reps} onChange={(e) => setReps(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select></label>
        </div>
      </details>
      <label>Anotação (opcional)<input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ex.: comparar o local com o Groq na identificação de stakeholders" /></label>
      <ErrorBox error={create.error} />
      <div className="row">
        <button className="primary" disabled={!taskExec || chosen.length === 0 || chosen.length > 6 || !strategies.length || total > 30 || create.isPending}>
          <Icon name="play" />Comparar ({total} tentativa{total === 1 ? "" : "s"})</button>
        {total > 30 && <span className="badge err">máximo de 30 tentativas</span>}
        <button type="button" className="ghost" onClick={onCancel}>Cancelar</button>
        <span className="muted small">As tentativas rodam em fila; com o modelo local, cada uma pode levar minutos.</span>
      </div>
    </form>
  );
}

export function TrialStatus({ status }: { status: string }) {
  const map: Record<string, string> = { queued: "queued", running: "running", completed: "completed", failed: "failed", cancelled: "superseded" };
  const label: Record<string, string> = { queued: "na fila", running: "rodando", completed: "concluída", failed: "falhou", cancelled: "cancelada" };
  return <span className={`badge ${map[status] ?? ""}`}>{label[status] ?? status}</span>;
}

