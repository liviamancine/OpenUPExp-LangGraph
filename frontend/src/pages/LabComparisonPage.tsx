import { Fragment, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LabDetail, LabMetrics, LabOutput, LabTrialT } from "../api/types";
import { taskName } from "../bpmn/names";
import Icon from "../components/Icon";
import { ErrorBox, Loading, PhaseChip, fieldLabel, fmtDate, show } from "../components/ui";
import { TrialStatus } from "./LabPage";

type Column = { key: string; titulo: string; sub: string; status: string; metrics: LabMetrics; output: LabOutput[]; trial?: LabTrialT };

const secs = (ms?: number | null) => (ms == null ? "—" : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

const ROWS: { label: string; help?: string; value: (m: LabMetrics) => ReactNode; tone?: (m: LabMetrics) => string }[] = [
  { label: "Formato aceito", help: "A resposta veio no formato que a plataforma espera (contrato BAML).",
    value: (m) => (m.contrato_valido == null ? "—" : m.contrato_valido ? "sim" : "não"),
    tone: (m) => (m.contrato_valido === false ? "err" : m.contrato_valido ? "ok" : "") },
  { label: "Itens produzidos", value: (m) => m.itens ?? "—" },
  { label: "Itens que faltaram", help: "Entradas que deveriam ter uma saída e ficaram sem.",
    value: (m) => (m.itens_faltantes ? (m.itens_faltantes.length ? m.itens_faltantes.join(", ") : "nenhum") : "—"),
    tone: (m) => (m.itens_faltantes?.length ? "warn" : "") },
  { label: "Pontos em aberto", help: "Informações que o modelo declarou não encontrar nas entradas (lacunas).", value: (m) => m.lacunas ?? "—" },
  { label: "Citações conferidas", help: "Citações que a plataforma encontrou literalmente na fonte.",
    value: (m) => (m.evidencias ? (m.evidencias.total ? `${m.evidencias.verificadas} de ${m.evidencias.total}` : "sem citações") : "—"),
    tone: (m) => (m.evidencias && m.evidencias.nao_verificadas > 0 ? "warn" : "") },
  { label: "Mesmos trechos recuperados", help: "Se a busca nos documentos trouxe exatamente os mesmos trechos da execução original.",
    value: (m) => (m.recuperacao ? (m.recuperacao.identica ? `sim (${m.recuperacao.trechos})` : `não (${m.recuperacao.trechos})`) : "—"),
    tone: (m) => (m.recuperacao && !m.recuperacao.identica ? "warn" : "") },
  { label: "Chamadas à IA", value: (m) => (m.chamadas == null ? "—" : `${m.chamadas}${m.chamadas_com_erro ? ` (${m.chamadas_com_erro} com erro)` : ""}`) },
  { label: "Tokens lidos / escritos", value: (m) => (m.input_tokens == null ? "—" : `${m.input_tokens.toLocaleString("pt-BR")} / ${(m.output_tokens ?? 0).toLocaleString("pt-BR")}`) },
  { label: "Tempo de resposta", value: (m) => secs(m.latency_ms) },
];

export default function LabComparisonPage() {
  const { comparisonId = "" } = useParams();
  const d = useQuery({
    queryKey: ["lab", comparisonId], queryFn: () => api.get<LabDetail>(`/lab/comparisons/${comparisonId}`),
    refetchInterval: (q) => (q.state.data?.tentativas.some((t) => t.status === "queued" || t.status === "running") ? 4000 : false),
  });
  if (d.isLoading) return <Loading what="Carregando a comparação" />;
  if (!d.data) return <ErrorBox error={d.error} />;
  const c = d.data;
  const cols: Column[] = [
    { key: "original", titulo: c.original.nome, sub: c.original.modelo, status: "completed", metrics: c.original.metrics, output: c.original.output },
    ...c.tentativas.map((t) => ({ key: t.id, titulo: t.modelo ?? "—", sub: t.model ?? "", status: t.status, metrics: t.metrics, output: t.output, trial: t })),
  ];
  const pending = c.tentativas.filter((t) => t.status === "queued" || t.status === "running").length;

  return (
    <div className="stack">
      <div>
        <Link to="/laboratorio" className="back"><Icon name="arrowLeft" size={14} />Laboratório</Link>
        <div className="page-head">
          <span className="phase-icon" style={{ background: "var(--p2-soft)", color: "var(--p2)" }}><Icon name="chart" size={24} /></span>
          <div className="grow">
            <h1>{taskName(c.task_id, c.nome)}</h1>
            <div className="subtitle row" style={{ gap: 8 }}>
              <PhaseChip phase={c.fase} /><span>{c.task_id} · {c.projeto} · criada em {fmtDate(c.created_at)} ·{" "}
                <Link to={`/execucoes/${c.run_id}`}>execução original</Link></span>
            </div>
            {c.notes && <div className="small" style={{ marginTop: 4 }}><Icon name="message" size={13} /> {c.notes}</div>}
          </div>
        </div>
      </div>

      {pending > 0 && <div className="banner running"><span className="banner-icon"><span className="spinner" /></span>
        <div className="grow"><div className="banner-title">{pending} tentativa(s) em andamento</div>
          <div className="muted">Rodam uma de cada vez. A página se atualiza sozinha.</div></div></div>}
      {c.prompts_mudaram && <div className="alert warn"><Icon name="alert" /><div>Os prompts mudaram desde a execução original.
        A coluna "Execução original" usou outra versão dos prompts; as tentativas usam a atual.</div></div>}

      <div className="card" style={{ overflowX: "auto" }}>
        <div className="card-head"><span className="icon-bubble"><Icon name="chart" /></span>
          <span className="grow"><h2>Comparação</h2><div className="muted small">Todas as colunas receberam o mesmo material de entrada
            (pacote <span className="mono">{c.package_sha256.slice(0, 10)}</span>).</div></span></div>
        <table className="small" style={{ minWidth: 220 + cols.length * 200 }}>
          <thead>
            <tr><th style={{ width: 220 }}></th>
              {cols.map((col) => (
                <th key={col.key} style={{ textTransform: "none", letterSpacing: 0 }}>
                  <div className="strong" style={{ color: "var(--text)", fontSize: 14 }}>
                    {col.trial?.local && <Icon name="lock" size={13} />} {col.titulo}</div>
                  <div className="tiny muted mono">{col.sub}</div>
                  <div style={{ marginTop: 4 }}>{col.trial ? <TrialStatus status={col.status} /> : <span className="badge">referência</span>}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label}>
                <td><strong>{row.label}</strong>{row.help && <div className="tiny muted">{row.help}</div>}</td>
                {cols.map((col) => (
                  <td key={col.key}>{col.status === "completed" || col.status === "failed"
                    ? <span className={row.tone?.(col.metrics) ? `badge ${row.tone(col.metrics)}` : ""}>{row.value(col.metrics)}</span>
                    : <span className="muted">—</span>}</td>
                ))}
              </tr>
            ))}
            <tr>
              <td><strong>Sua nota</strong><div className="tiny muted">De 1 (ruim) a 5 (ótimo), pela utilidade do resultado.</div></td>
              {cols.map((col) => <td key={col.key}>{col.trial ? <Rating trial={col.trial} onSaved={() => d.refetch()} /> : <span className="muted">—</span>}</td>)}
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card stack">
        <div className="card-head"><span className="icon-bubble"><Icon name="layers" /></span><h2>Resultados lado a lado</h2></div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols.length}, minmax(280px, 1fr))`, gap: 12, overflowX: "auto" }}>
          {cols.map((col) => <OutputColumn key={col.key} col={col} canEdit={c.pode_editar} onChange={() => d.refetch()} />)}
        </div>
      </div>
    </div>
  );
}

function OutputColumn({ col, canEdit, onChange }: { col: Column; canEdit: boolean; onChange: () => void }) {
  const cancel = useMutation({ mutationFn: () => api.post(`/lab/trials/${col.trial!.id}/cancel`), onSuccess: onChange });
  return (
    <div className="stack tight" style={{ minWidth: 0 }}>
      <div className="row" style={{ gap: 6 }}><strong className="grow">{col.titulo}</strong>
        {col.trial ? <TrialStatus status={col.status} /> : <span className="badge">referência</span>}</div>
      {col.trial?.status === "queued" && canEdit && <button className="small ghost" onClick={() => cancel.mutate()}>Cancelar</button>}
      {col.trial?.status === "running" && <div className="loading"><span className="spinner" />Rodando…</div>}
      {col.trial?.error && <div className="alert err small"><Icon name="xCircle" /><div style={{ wordBreak: "break-word" }}>{col.trial.error}</div></div>}
      {col.output.map((o) => <ArtifactOutput key={o.artifact} o={o} />)}
      {col.trial && col.trial.calls.length > 0 && (
        <details className="tiny muted"><summary>Chamadas ({col.trial.calls.length})</summary>
          {col.trial.calls.map((x, i) => <div key={i}>{x.function} · {x.status} · {secs(x.latency_ms)}{x.error ? ` · ${x.error}` : ""}</div>)}
        </details>
      )}
      <ErrorBox error={cancel.error} />
    </div>
  );
}

const HIDE = new Set(["id", "origem", "evidencias", "lacunas", "lacuna", "baseada_em", "verificacao", "fundamentacao_verificada"]);

function ArtifactOutput({ o }: { o: LabOutput }) {
  const lists = Object.entries(o.content).filter(([, v]) => Array.isArray(v) && v.some((x) => typeof x === "object"));
  const scalars = Object.entries(o.content).filter(([k, v]) => !HIDE.has(k) && !(Array.isArray(v) && v.some((x) => typeof x === "object")));
  return (
    <div className="item-card stack tight">
      <div className="strong small">{o.titulo}</div>
      {scalars.length > 0 && (
        <dl className="kv small">{scalars.map(([k, v]) => <Fragment key={k}><dt>{fieldLabel(k)}</dt><dd>{show(v)}</dd></Fragment>)}</dl>
      )}
      {lists.map(([k, items]) => (
        <div key={k} className="stack tight">
          {(items as Record<string, unknown>[]).map((it, i) => (
            <div key={i} className="quote small">
              {Object.entries(it).filter(([kk]) => !HIDE.has(kk)).map(([kk, vv]) => (
                <div key={kk}><span className="muted">{fieldLabel(kk)}:</span> {show(vv)}</div>
              ))}
              {Array.isArray(it.lacunas) && it.lacunas.length > 0 && <div className="tiny" style={{ color: "var(--warn)" }}>
                {it.lacunas.length} ponto(s) em aberto</div>}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Rating({ trial, onSaved }: { trial: LabTrialT; onSaved: () => void }) {
  const mine = trial.notas.find((n) => n.minha);
  const [nota, setNota] = useState(mine?.nota ?? 0);
  const [comentario, setComentario] = useState(mine?.comentario ?? "");
  const save = useMutation({ mutationFn: () => api.post(`/lab/trials/${trial.id}/rating`, { nota, comentario: comentario || null }), onSuccess: onSaved });
  if (trial.status !== "completed") return <span className="muted">—</span>;
  const avg = trial.notas.length ? (trial.notas.reduce((a, n) => a + n.nota, 0) / trial.notas.length).toFixed(1) : null;
  return (
    <div className="stack tight">
      <div className="row" style={{ gap: 2 }} role="radiogroup" aria-label="Nota">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" className="ghost small" aria-label={`Nota ${n}`} aria-pressed={nota >= n}
            style={{ padding: "2px 4px", color: nota >= n ? "#f59e0b" : "var(--muted)", fontSize: 18 }} onClick={() => setNota(n)}>★</button>
        ))}
      </div>
      <input className="small" value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Comentário (opcional)" />
      <button className="small" disabled={!nota || save.isPending} onClick={() => save.mutate()}>{mine ? "Atualizar nota" : "Salvar nota"}</button>
      {avg && <div className="tiny muted">Média: {avg} ({trial.notas.length} avaliação(ões))</div>}
      <ErrorBox error={save.error} />
    </div>
  );
}
