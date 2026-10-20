import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ArtifactSummary, HitlDetail, ItemComment } from "../api/types";
import ArtifactView from "../components/ArtifactView";
import { ErrorBox, Loading, Markdown, Status, fmtDate } from "../components/ui";
import { useRunEvents } from "../hooks";

const DECISION_LABEL: Record<string, string> = {
  approve: "Aprovar a Visão",
  revisit_1_1: "Revisitar 1.1 Prepare Explainability Vision",
  revisit_1_2: "Revisitar 1.2 Develop Explainability Vision",
};

const REVIEWABLE = new Set([
  "vision.problem", "vision.positioning", "vision.stakeholders", "vision.stakeholder_needs", "vision.explainability_needs",
  "vision.complementary_requirements", "vision.limits", "glossary", "vision.draft",
]);

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
  const [decision, setDecision] = useState("approve");
  const [comment, setComment] = useState("");
  const [itemComments, setItemComments] = useState<ItemComment[]>([]);
  const submit = useMutation({
    mutationFn: () => api.post(`/hitl/${requestId}/responses`, { decision, comentario: comment || null, item_comments: itemComments }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["inbox"] }); navigate(`/execucoes/${runId}`); },
  });

  if (req.isLoading) return <Loading />;
  if (!req.data) return <ErrorBox error={req.error} />;
  const r = req.data;
  const sections = (arts.data ?? []).filter((a) => REVIEWABLE.has(a.artifact_type));
  const current = sections.find((a) => a.artifact_type === selected) ?? sections.find((a) => a.artifact_type === "vision.draft");
  const outcome = r.payload.outcomes[decision];
  const needsComment = outcome?.comment_required && !comment.trim();
  const approvalBlocked = decision === "approve" && r.stale.length > 0;

  return (
    <div className="stack">
      <div className="row">
        <div className="grow">
          <div className="small"><Link to={`/execucoes/${r.run_id}`}>← execução</Link> · {r.projeto?.nome}</div>
          <h1>{r.payload.name ?? r.task_id} <span className="muted small">iteração {r.iteracao}</span></h1>
          <div className="muted small">Aprovação individual do Engenheiro de Requisitos · aberta em {fmtDate(r.created_at)} · <Status value={r.status} /></div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "260px minmax(0, 1fr) 340px", gap: 12, alignItems: "start" }}>
        <div className="card stack">
          <h3>Seções</h3>
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
          <h3 style={{ marginTop: 8 }}>Checklist automático</h3>
          <div className="muted small">Verificações objetivas (1.3.1); não substituem sua revisão.</div>
          {r.review_report?.checks.map((c) => (
            <div key={c.id} className="small">
              <span className={`badge ${c.ok ? "ok" : "warn"}`}>{c.ok ? "ok" : "atenção"}</span> {c.descricao}
              {!c.ok && c.detalhes.length > 0 && <div className="muted mono">{c.detalhes.join(", ")}</div>}
            </div>
          ))}
        </div>

        <div className="card">
          {current ? (
            current.artifact_type === "vision.draft"
              ? <DraftPreview runId={r.run_id} />
              : <ArtifactView key={current.id} versionId={current.id}
                  onComment={(c) => setItemComments((xs) => [...xs, c])}
                  onNewVersion={() => arts.refetch()} />
          ) : <Loading />}
        </div>

        <form className="card stack" onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}>
          <h2>Decisão</h2>
          <div className="muted small">Conforme o BPMN, o Engenheiro decide se revisita 1.1 ou 1.2 com base no problema identificado.</div>
          {Object.keys(r.payload.outcomes).map((k) => (
            <label key={k} className="inline">
              <input type="radio" name="decision" value={k} checked={decision === k} onChange={() => setDecision(k)} />
              {DECISION_LABEL[k] ?? k}
            </label>
          ))}
          <label>Comentário {outcome?.comment_required && "(obrigatório)"}
            <textarea value={comment} onChange={(e) => setComment(e.target.value)}
              placeholder="O que precisa mudar? O comentário é entregue aos agentes que refazem o subprocesso." />
          </label>
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
          <button className="primary" disabled={r.status !== "open" || needsComment || approvalBlocked || submit.isPending}>
            Registrar decisão</button>
          {r.respostas.length > 0 && (
            <div className="stack small">
              <strong>Histórico</strong>
              {r.respostas.map((x) => <div key={x.id}>{fmtDate(x.created_at)} · {x.decision} {x.comentario && `— ${x.comentario}`}</div>)}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

function DraftPreview({ runId }: { runId: string }) {
  const doc = useQuery({ queryKey: ["artifacts", runId, "doc"], queryFn: () => api.get<string>(`/runs/${runId}/document`) });
  return doc.data ? (
    <div className="stack">
      <div className="alert info small">Prévia do Documento de Visão com as versões atuais (inclui suas edições). Comente nas seções à esquerda.</div>
      <Markdown>{doc.data}</Markdown>
    </div>
  ) : <Loading />;
}
