import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ArtifactSummary, HitlDetail, ItemComment } from "../api/types";
import ArtifactView from "../components/ArtifactView";
import { DECISION_LABEL, ErrorBox, Loading, Markdown, Status, fmtDate } from "../components/ui";
import { useRunEvents } from "../hooks";

const PREVIEW = "__preview__";
const POSITIONS = [
  { id: "concordo", label: "Concordo" },
  { id: "ressalvas", label: "Concordo com ressalvas" },
  { id: "objecao", label: "Objeção (bloqueia o encerramento)" },
];

const KIND_INTRO: Record<string, string> = {
  approval: "Aprovação individual do Engenheiro de Requisitos",
  consensus: "Rodada de consenso: participantes registram posição; o Engenheiro encerra ou pede retorno",
  input: "Entrada humana: material de elicitação para a tarefa 2.2.1",
};

export default function ReviewPage() {
  const { requestId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const req = useQuery({ queryKey: ["hitl", requestId], queryFn: () => api.get<HitlDetail>(`/hitl/${requestId}`) });
  const runId = req.data?.run_id;
  useRunEvents(runId);
  const arts = useQuery({ queryKey: ["artifacts", runId], enabled: !!runId,
    queryFn: () => api.get<ArtifactSummary[]>(`/runs/${runId}/artifacts`) });
  const [selected, setSelected] = useState<string | null>(null);
  const [itemComments, setItemComments] = useState<ItemComment[]>([]);

  if (req.isLoading) return <Loading />;
  if (!req.data) return <ErrorBox error={req.error} />;
  const r = req.data;
  const sections = (arts.data ?? []).filter((a) => a.secao && !a.artifact_type.endsWith(".draft"));
  const current = sections.find((a) => a.artifact_type === selected);
  const plan = sections.find((a) => a.artifact_type === "elicitation.plan");
  const isEngineer = r.meu_papel === "requirements_engineer" || r.meu_papel === "admin";
  const participantRoles = (r.policy.participant_roles as string[] | undefined) ?? [];
  const canPosition = r.meu_papel === "admin" || participantRoles.includes(r.meu_papel);
  const done = () => { qc.invalidateQueries({ queryKey: ["inbox"] }); navigate(`/execucoes/${r.run_id}`); };

  return (
    <div className="stack">
      <div className="row">
        <div className="grow">
          <div className="small"><Link to={`/execucoes/${r.run_id}`}>← execução</Link> · {r.projeto?.nome}</div>
          <h1>{r.payload.name ?? r.task_id} <span className="muted small">{r.task_id} · iteração {r.iteracao}</span></h1>
          <div className="muted small">{KIND_INTRO[r.kind] ?? r.kind} · aberta em {fmtDate(r.created_at)}
            {r.due_at && <> · prazo {fmtDate(r.due_at)}</>} · <Status value={r.status} /></div>
        </div>
      </div>

      {r.kind === "input" ? (
        <div className="split">
          <div className="card">
            {plan ? <ArtifactView versionId={plan.id} /> : <Loading what="Carregando o plano de elicitação" />}
          </div>
          <InputForm r={r} isEngineer={isEngineer} onDone={done} />
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "260px minmax(0, 1fr) 340px", gap: 12, alignItems: "start" }}>
          <div className="card stack">
            <h3>Seções</h3>
            <div className={`list-item ${!current ? "active" : ""}`} onClick={() => setSelected(PREVIEW)}>
              <div>Prévia do documento</div>
              <div className="small muted">versões atuais, com suas edições</div>
            </div>
            {sections.map((a) => (
              <div key={a.id} className={`list-item ${current?.id === a.id ? "active" : ""}`} onClick={() => setSelected(a.artifact_type)}>
                <div className="row" style={{ gap: 6 }}>
                  <span className="grow">{a.title}</span>
                  {a.origin === "human_edit" && <span className="badge human_edit">editado</span>}
                  {a.status === "stale" && <span className="badge stale">!</span>}
                </div>
                <div className="small muted">v{a.version_no}{a.itens != null ? ` · ${a.itens} itens` : ""}
                  {r.review_report?.lacunas_por_artefato?.[a.artifact_type] ? ` · ${r.review_report.lacunas_por_artefato[a.artifact_type]} lacunas` : ""}</div>
              </div>
            ))}
            {r.review_report && (
              <>
                <h3 style={{ marginTop: 8 }}>Checklist automático</h3>
                <div className="muted small">Verificações objetivas da pré-revisão; não substituem sua revisão.</div>
                {r.review_report.checks.map((c) => (
                  <div key={c.id} className="small">
                    <span className={`badge ${c.ok ? "ok" : "warn"}`}>{c.ok ? "ok" : "atenção"}</span> {c.descricao}
                    {!c.ok && c.detalhes.length > 0 && <div className="muted mono">{c.detalhes.join(", ")}</div>}
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="card">
            {current
              ? <ArtifactView key={current.id} versionId={current.id}
                  onComment={(c) => setItemComments((xs) => [...xs, c])}
                  onNewVersion={() => arts.refetch()} />
              : <DraftPreview runId={r.run_id} />}
          </div>

          <div className="stack">
            {r.kind === "consensus" && <ConsensusPanel r={r} canPosition={canPosition} itemComments={itemComments}
              onPosted={() => { setItemComments([]); req.refetch(); }} />}
            {isEngineer
              ? <DecisionForm r={r} itemComments={itemComments} setItemComments={setItemComments} onDone={done} />
              : <div className="card muted small">A decisão deste ponto cabe ao Engenheiro de Requisitos.</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function DecisionForm({ r, itemComments, setItemComments, onDone }: {
  r: HitlDetail; itemComments: ItemComment[]; setItemComments: (c: ItemComment[]) => void; onDone: () => void;
}) {
  const outcomes = Object.keys(r.payload.outcomes);
  const [decision, setDecision] = useState(outcomes[0] ?? "approve");
  const [comment, setComment] = useState("");
  const submit = useMutation({
    mutationFn: () => api.post(`/hitl/${r.id}/responses`, { decision, comentario: comment || null, item_comments: itemComments }),
    onSuccess: onDone,
  });
  const outcome = r.payload.outcomes[decision];
  const tally = r.consenso;
  const closeNeedsJustification = r.kind === "consensus" && decision === "close" && !!tally
    && (tally.objecao > 0 || tally.participantes === 0);
  const commentRequired = !!outcome?.comment_required || closeNeedsJustification;
  const approvalBlocked = decision === "approve" && r.stale.length > 0;

  return (
    <form className="card stack" onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}>
      <h2>Decisão</h2>
      {r.kind === "approval" && <div className="muted small">Conforme o BPMN, o Engenheiro decide qual subprocesso revisitar com base no problema identificado.</div>}
      {outcomes.map((k) => (
        <label key={k} className="inline">
          <input type="radio" name="decision" value={k} checked={decision === k} onChange={() => setDecision(k)} />
          {DECISION_LABEL[k] ?? k}
        </label>
      ))}
      <label>Comentário {commentRequired && "(obrigatório)"}
        <textarea value={comment} onChange={(e) => setComment(e.target.value)}
          placeholder="O que precisa mudar? O comentário é entregue aos agentes que refazem o subprocesso." />
      </label>
      {closeNeedsJustification && tally && <div className="alert warn small">
        {tally.participantes === 0 ? "Nenhum participante registrou posição." : `${tally.objecao} objeção(ões) registrada(s).`}
        {" "}Encerrar exige justificativa, que fica registrada no ERD.</div>}
      {itemComments.length > 0 && (
        <div className="stack small">
          <strong>Comentários por item ({itemComments.length})</strong>
          {itemComments.map((c, i) => (
            <div key={i} className="row" style={{ gap: 6 }}>
              <span className="mono">{c.alvo}</span><span className="grow">{c.texto}</span>
              <button type="button" onClick={() => setItemComments(itemComments.filter((_, j) => j !== i))}>×</button>
            </div>
          ))}
        </div>
      )}
      {approvalBlocked && <div className="alert warn small">Há artefatos desatualizados: {r.stale.join(", ")}. Solicite retorno.</div>}
      <ErrorBox error={submit.error} />
      <button className="primary" disabled={r.status !== "open" || (commentRequired && !comment.trim()) || approvalBlocked || submit.isPending}>
        Registrar decisão</button>
      <History r={r} />
    </form>
  );
}

function ConsensusPanel({ r, canPosition, itemComments, onPosted }: {
  r: HitlDetail; canPosition: boolean; itemComments: ItemComment[]; onPosted: () => void;
}) {
  const [posicao, setPosicao] = useState("concordo");
  const [comment, setComment] = useState("");
  const post = useMutation({
    mutationFn: () => api.post(`/hitl/${r.id}/positions`, { posicao, comentario: comment || null, item_comments: itemComments }),
    onSuccess: () => { setComment(""); onPosted(); },
  });
  const tally = r.consenso;
  const positions = r.respostas.filter((x) => POSITIONS.some((p) => p.id === x.decision));
  return (
    <form className="card stack" onSubmit={(e) => { e.preventDefault(); post.mutate(); }}>
      <h2>Consenso</h2>
      <div className="muted small">Regra provisória (A-13): o consenso fecha sem objeção bloqueante. Vale a última posição de cada pessoa.</div>
      {tally && (
        <div className="row small">
          <span className="badge ok">{tally.concordo} concordo</span>
          <span className="badge warn">{tally.ressalvas} ressalvas</span>
          <span className="badge err">{tally.objecao} objeções</span>
          <span className="muted">{tally.participantes} participante(s)</span>
        </div>
      )}
      {positions.map((x) => (
        <div key={x.id} className="small"><strong>{x.user_nome ?? "—"}</strong> · <Status value={x.decision} />
          {x.comentario && <> — {x.comentario}</>}
          {x.item_comments.map((c, i) => <div key={i} className="muted"><span className="mono">{c.alvo}</span>: {c.texto}</div>)}
        </div>
      ))}
      {canPosition && r.status === "open" && (
        <>
          <h3>Sua posição</h3>
          {POSITIONS.map((p) => (
            <label key={p.id} className="inline">
              <input type="radio" name="posicao" checked={posicao === p.id} onChange={() => setPosicao(p.id)} /> {p.label}
            </label>
          ))}
          <label>Comentário {posicao !== "concordo" && "(obrigatório)"}
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="O que falta ou precisa mudar?" />
          </label>
          {itemComments.length > 0 && <div className="muted small">{itemComments.length} comentário(s) por item serão anexados.</div>}
          <ErrorBox error={post.error} />
          <button disabled={post.isPending || (posicao !== "concordo" && !comment.trim() && !itemComments.length)}>Registrar posição</button>
        </>
      )}
    </form>
  );
}

function InputForm({ r, isEngineer, onDone }: { r: HitlDetail; isEngineer: boolean; onDone: () => void }) {
  const qc = useQueryClient();
  const [files, setFiles] = useState<FileList | null>(null);
  const upload = useMutation({
    mutationFn: async () => {
      for (const f of Array.from(files ?? [])) {
        const form = new FormData();
        form.append("file", f);
        form.append("source_kind", "elicitacao");
        await api.upload(`/projects/${r.projeto?.id}/sources`, form);
      }
    },
    onSuccess: () => { setFiles(null); qc.invalidateQueries({ queryKey: ["hitl", r.id] }); },
  });
  const material = r.material ?? [];
  return (
    <div className="stack">
      <div className="card stack">
        <h2>Material de elicitação</h2>
        <div className="muted small">
          Conduza a elicitação conforme o plano ao lado e envie o material (transcrições, atas, respostas de questionários).
          Cada stakeholder recebe só os trechos do material relacionados a ele, recuperados por busca híbrida; toda necessidade
          extraída precisa citar um trecho literal, conferido mecanicamente.
        </div>
        {material.length === 0 ? <div className="alert warn small">Nenhum documento de elicitação enviado.</div> : (
          <ul className="small">{material.map((m) => <li key={m.id}>{m.arquivo} {m.paginas ? `· ${m.paginas} p.` : ""}</li>)}</ul>
        )}
        {isEngineer && r.status === "open" && (
          <>
            <input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => setFiles(e.target.files)} />
            <ErrorBox error={upload.error} />
            <button type="button" disabled={!files?.length || upload.isPending} onClick={() => upload.mutate()}>Enviar documentos</button>
          </>
        )}
      </div>
      {isEngineer
        ? <DecisionForm r={r} itemComments={[]} setItemComments={() => undefined} onDone={onDone} />
        : <div className="card muted small">O envio do material cabe ao Engenheiro de Requisitos.</div>}
    </div>
  );
}

function History({ r }: { r: HitlDetail }) {
  const decisions = r.respostas.filter((x) => !POSITIONS.some((p) => p.id === x.decision));
  if (!decisions.length) return null;
  return (
    <div className="stack small">
      <strong>Histórico</strong>
      {decisions.map((x) => <div key={x.id}>{fmtDate(x.created_at)} · {DECISION_LABEL[x.decision] ?? x.decision} {x.comentario && `— ${x.comentario}`}</div>)}
    </div>
  );
}

function DraftPreview({ runId }: { runId: string }) {
  const doc = useQuery({ queryKey: ["artifacts", runId, "doc"], queryFn: () => api.get<string>(`/runs/${runId}/document`) });
  return doc.data ? (
    <div className="stack">
      <div className="alert info small">Prévia do documento com as versões atuais (inclui suas edições). Comente nas seções à esquerda.</div>
      <Markdown>{doc.data}</Markdown>
    </div>
  ) : <Loading />;
}
