import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ArtifactSummary, HitlDetail, ItemComment } from "../api/types";
import { taskName } from "../bpmn/names";
import ArtifactView from "../components/ArtifactView";
import Icon, { type IconName } from "../components/Icon";
import { ErrorBox, Hint, Loading, Markdown, PHASES, PhaseIcon, Status, decisionHelp, decisionLabel, fmtDate } from "../components/ui";
import { useRunEvents } from "../hooks";

const PREVIEW = "__preview__";
const POSITIONS: { id: string; label: string; help: string; tone: string; icon: IconName }[] = [
  { id: "concordo", label: "Concordo", help: "Está bom como está.", tone: "ok", icon: "thumbsUp" },
  { id: "ressalvas", label: "Concordo, com observações", help: "Pode seguir, mas deixo sugestões.", tone: "warn", icon: "message" },
  { id: "objecao", label: "Discordo", help: "Algo precisa mudar antes de seguir.", tone: "err", icon: "xCircle" },
];

const KIND_INTRO: Record<string, { title: string; steps: string[] }> = {
  approval: {
    title: "Revise e aprove",
    steps: ["Abra cada parte no menu à esquerda e leia com atenção.",
      "Para corrigir algo, clique em Editar esta parte: sua edição vira uma nova versão.",
      "Quando estiver tudo certo, aprove."],
  },
  consensus: {
    title: "Opinião da equipe",
    steps: ["Cada pessoa lê o resultado e diz se concorda.", "Quem discorda explica o motivo.",
      "O responsável ajusta o que for preciso, editando as partes, e encerra a rodada."],
  },
  input: {
    title: "Envie o material das conversas",
    steps: ["Converse com as pessoas seguindo o roteiro ao lado.", "Envie as transcrições, atas ou anotações.",
      "Clique em continuar: a IA lê o material e extrai as necessidades."],
  },
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
  const [visited, setVisited] = useState<Set<string>>(new Set());
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
  const intro = KIND_INTRO[r.kind] ?? KIND_INTRO.approval;
  const phase = r.phase ?? r.task_id.split(".")[0];
  const failing = r.review_report?.checks.filter((c) => !c.ok) ?? [];
  // Comentários por item só servem à opinião da equipe; na aprovação, quem corrige é o próprio Engenheiro, editando.
  const commentsEnabled = r.kind === "consensus";
  const order = [PREVIEW, ...sections.map((a) => a.artifact_type)];
  const position = current ? order.indexOf(current.artifact_type) : 0;
  const open = (key: string) => {
    setSelected(key);
    if (key !== PREVIEW) setVisited((v) => new Set(v).add(key));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const titleOf = (key: string) => key === PREVIEW ? "Documento completo"
    : sections.find((a) => a.artifact_type === key)?.title ?? key;

  return (
    <div className="stack">
      <div>
        <Link to={`/execucoes/${r.run_id}`} className="back"><Icon name="arrowLeft" size={14} />Voltar à etapa · {r.projeto?.nome}</Link>
        <div className="page-head">
          <PhaseIcon phase={phase} size={26} />
          <div className="grow">
            <h1>{intro.title}</h1>
            <div className="subtitle">Etapa {phase} · {PHASES[phase]?.titulo} · {taskName(r.task_id, r.payload.name)}
              {r.iteracao > 1 && <> · {r.iteracao}ª rodada</>} · desde {fmtDate(r.created_at)}
              {r.due_at && <> · prazo {fmtDate(r.due_at)}</>}</div>
          </div>
          <Status value={r.status} />
        </div>
      </div>

      <div className="card">
        <div className="journey" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          {intro.steps.map((s, i) => (
            <div key={i} className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start", gap: 10 }}>
              <span className="avatar" style={{ width: 28, height: 28, fontSize: 13, background: "var(--accent)" }}>{i + 1}</span>
              <span className="small">{s}</span>
            </div>
          ))}
        </div>
      </div>

      {r.kind === "input" ? (
        <div className="split">
          <div className="card">
            {plan ? <ArtifactView versionId={plan.id} /> : <Loading what="Carregando o roteiro das conversas" />}
          </div>
          <InputForm r={r} isEngineer={isEngineer} onDone={done} />
        </div>
      ) : (
        <div className="review-grid">
          <div className="card stack tight">
            <h3>Partes do documento</h3>
            <div className="tiny muted">{visited.size} de {sections.length} partes abertas</div>
            <div className={`list-item ${!current ? "active" : ""}`} onClick={() => open(PREVIEW)}>
              <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}><Icon name="file" size={16} /><strong>Documento completo</strong></div>
              <div className="tiny muted">como vai ficar, com suas edições</div>
            </div>
            {sections.map((a) => {
              const gaps = r.review_report?.lacunas_por_artefato?.[a.artifact_type];
              return (
                <div key={a.id} className={`list-item ${current?.id === a.id ? "active" : ""}`} onClick={() => open(a.artifact_type)}>
                  <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
                    <span className="grow small strong">{a.title}</span>
                    {visited.has(a.artifact_type) && <span className="badge ok" title="você já abriu esta parte"><Icon name="check" size={11} /></span>}
                    {a.origin === "human_edit" && <span className="badge human_edit" title="editada por você"><Icon name="edit" size={11} /></span>}
                    {a.status === "stale" && <span className="badge stale" title="confira: algo de que esta parte depende mudou"><Icon name="alert" size={11} /></span>}
                  </div>
                  <div className="tiny muted">{a.itens != null ? `${a.itens} itens` : "texto"}{gaps ? ` · ${gaps} ponto(s) em aberto` : ""}
                    {a.status === "stale" ? " · confira" : ""}</div>
                </div>
              );
            })}
            {r.review_report && (
              <>
                <h3 style={{ marginTop: 10 }}>Verificação automática</h3>
                {failing.length === 0
                  ? <div className="alert ok small"><Icon name="checkCircle" />Tudo certo nas {r.review_report.checks.length} verificações.</div>
                  : <div className="alert warn small"><Icon name="alert" />{failing.length} ponto(s) para olhar com atenção.</div>}
                <div className="checklist">
                  {r.review_report.checks.map((c) => (
                    <div key={c.id} className={`check-item small ${c.ok ? "ok" : "todo"}`}>
                      <Icon name={c.ok ? "checkCircle" : "alert"} size={15} />
                      <span>{c.descricao}{!c.ok && c.detalhes.length > 0 && <div className="muted mono">{c.detalhes.join(", ")}</div>}</span>
                    </div>
                  ))}
                </div>
                <div className="tiny muted">A verificação ajuda, mas não substitui a sua leitura.</div>
              </>
            )}
          </div>

          <div className="card stack">
            <div className="row" style={{ flexWrap: "nowrap", gap: 8 }}>
              <button type="button" className="ghost small" disabled={position <= 0} onClick={() => open(order[position - 1])}
                title={position > 0 ? titleOf(order[position - 1]) : undefined}><Icon name="arrowLeft" size={14} />Anterior</button>
              <span className="grow tiny muted" style={{ textAlign: "center", whiteSpace: "nowrap" }}>parte {position + 1} de {order.length}</span>
              <button type="button" className="ghost small" disabled={position >= order.length - 1} onClick={() => open(order[position + 1])}
                title={position < order.length - 1 ? titleOf(order[position + 1]) : undefined}>Próxima<Icon name="arrowRight" size={14} /></button>
            </div>
            {current
              ? <ArtifactView key={current.id} versionId={current.id}
                  onComment={commentsEnabled ? (c) => setItemComments((xs) => [...xs, c]) : undefined}
                  onNewVersion={() => arts.refetch()} />
              : <DraftPreview runId={r.run_id} />}
          </div>

          <div className="stack">
            {r.kind === "consensus" && <ConsensusPanel r={r} canPosition={canPosition} itemComments={itemComments}
              onPosted={() => { setItemComments([]); req.refetch(); }} />}
            {isEngineer
              ? <DecisionForm r={r} sections={sections} itemComments={itemComments} setItemComments={setItemComments} onDone={done} />
              : <div className="card"><Hint>Quem decide este ponto é o responsável pelos requisitos.</Hint></div>}
          </div>
        </div>
      )}
    </div>
  );
}

function DecisionForm({ r, sections = [], itemComments, setItemComments, onDone }: {
  r: HitlDetail; sections?: ArtifactSummary[]; itemComments: ItemComment[]; setItemComments: (c: ItemComment[]) => void;
  onDone: () => void;
}) {
  // A IA não refaz partes: os retornos (revisit_*) continuam no manifesto, fiéis ao BPMN, mas não aparecem aqui.
  const outcomes = Object.keys(r.payload.outcomes).filter((k) => !k.startsWith("revisit_"));
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
  const edited = sections.filter((a) => a.origin === "human_edit");
  const toCheck = sections.filter((a) => r.stale.includes(a.artifact_type));
  const openPoints = Object.values(r.review_report?.lacunas_por_artefato ?? {}).reduce((n, x) => n + x, 0);

  return (
    <form className="card stack" onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}>
      <div className="card-head"><span className="icon-bubble"><Icon name="flag" /></span><h2>Sua decisão</h2></div>
      {outcomes.length > 1 ? (
        <div className="choices">
          {outcomes.map((k) => (
            <label key={k} className={`choice ${decision === k ? "selected" : ""} ${k === "no_material" ? "tone-warn" : "tone-ok"}`}>
              <input type="radio" name="decision" value={k} checked={decision === k} onChange={() => setDecision(k)} />
              <span><div className="title">{decisionLabel(k)}</div><div className="help">{decisionHelp(k)}</div></span>
            </label>
          ))}
        </div>
      ) : <div className="small muted">{decisionHelp(decision)}</div>}
      {r.kind !== "input" && (
        <div className="checklist">
          <div className="check-item small ok"><Icon name="edit" size={15} />
            <span>{edited.length ? `Você editou ${edited.length} parte(s): ${edited.map((a) => a.title).join(", ")}.` : "Nenhuma parte editada."}</span></div>
          {openPoints > 0 && <div className="check-item small todo"><Icon name="help" size={15} />
            <span>{openPoints} ponto(s) em aberto (falta de informação). Dá para aprovar e tratar na próxima etapa.</span></div>}
        </div>
      )}
      {toCheck.length > 0 && <div className="alert warn small"><Icon name="alert" />
        <div>Confira antes de aprovar: <strong>{toCheck.map((a) => a.title).join(", ")}</strong>. Algo de que essas partes dependem mudou depois que foram feitas.</div></div>}
      <label>Comentário {commentRequired ? "(obrigatório)" : "(opcional)"}
        <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Algo que valha registrar?" />
      </label>
      {closeNeedsJustification && tally && <div className="alert warn small"><Icon name="alert" />
        <div>{tally.participantes === 0 ? "Ninguém deu opinião ainda." : `${tally.objecao} pessoa(s) discordaram.`}
          {" "}Para encerrar mesmo assim, explique o motivo — fica registrado no documento.</div></div>}
      {itemComments.length > 0 && (
        <div className="stack tight small">
          <strong>Comentários nos itens ({itemComments.length})</strong>
          {itemComments.map((c, i) => (
            <div key={i} className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
              <span className="badge">{c.alvo.split("#").pop()}</span><span className="grow">{c.texto}</span>
              <button type="button" className="ghost small" aria-label="Remover comentário"
                onClick={() => setItemComments(itemComments.filter((_, j) => j !== i))}><Icon name="x" size={14} /></button>
            </div>
          ))}
        </div>
      )}
      <ErrorBox error={submit.error} />
      <button className="primary big" disabled={r.status !== "open" || (commentRequired && !comment.trim()) || submit.isPending}>
        <Icon name="check" />{submit.isPending ? "Registrando…" : outcomes.length > 1 ? "Confirmar decisão" : decisionLabel(decision)}</button>
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
      <div className="card-head"><span className="icon-bubble"><Icon name="users" /></span><h2>Opinião da equipe</h2></div>
      {tally && (
        <div className="row small">
          <span className="badge ok"><Icon name="thumbsUp" size={12} />{tally.concordo} concordam</span>
          <span className="badge warn"><Icon name="message" size={12} />{tally.ressalvas} com observações</span>
          <span className="badge err"><Icon name="xCircle" size={12} />{tally.objecao} discordam</span>
        </div>
      )}
      <div className="tiny muted">Só dá para encerrar sem justificativa quando ninguém discorda. Vale a última opinião de cada pessoa.</div>
      {positions.map((x) => (
        <div key={x.id} className="small row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
          <span className="avatar" style={{ width: 28, height: 28, fontSize: 12 }}>{(x.user_nome ?? "?").slice(0, 1)}</span>
          <span className="grow"><strong>{x.user_nome ?? "—"}</strong> <Status value={x.decision} />
            {x.comentario && <div>{x.comentario}</div>}
            {x.item_comments.map((c, i) => <div key={i} className="muted"><span className="badge">{c.alvo.split("#").pop()}</span> {c.texto}</div>)}</span>
        </div>
      ))}
      {canPosition && r.status === "open" && (
        <>
          <h3>A sua opinião</h3>
          <div className="choices">
            {POSITIONS.map((p) => (
              <label key={p.id} className={`choice tone-${p.tone} ${posicao === p.id ? "selected" : ""}`}>
                <input type="radio" name="posicao" checked={posicao === p.id} onChange={() => setPosicao(p.id)} />
                <span><div className="title"><Icon name={p.icon} size={14} /> {p.label}</div><div className="help">{p.help}</div></span>
              </label>
            ))}
          </div>
          <label>Comentário {posicao !== "concordo" ? "(obrigatório)" : "(opcional)"}
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="O que falta ou precisa mudar?" />
          </label>
          {itemComments.length > 0 && <div className="muted small">{itemComments.length} comentário(s) em itens serão anexados.</div>}
          <ErrorBox error={post.error} />
          <button disabled={post.isPending || (posicao !== "concordo" && !comment.trim() && !itemComments.length)}>
            <Icon name="message" />Registrar minha opinião</button>
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
        <div className="card-head"><span className="icon-bubble"><Icon name="upload" /></span><h2>Material das conversas</h2></div>
        <div className="muted small">
          A IA lê, para cada pessoa, só os trechos do material que falam dela. Toda necessidade que ela extrair
          precisa citar um trecho literal do material — a plataforma confere.
        </div>
        {material.length === 0 ? <div className="alert warn small"><Icon name="alert" />Nenhum material enviado ainda.</div> : (
          <div className="stack tight">{material.map((m) => (
            <div key={m.id} className="row small" style={{ gap: 8 }}><Icon name="file" size={16} />{m.arquivo}
              {m.paginas ? <span className="muted">· {m.paginas} p.</span> : null}</div>))}</div>
        )}
        {isEngineer && r.status === "open" && (
          <>
            <input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => setFiles(e.target.files)} />
            <ErrorBox error={upload.error} />
            <button type="button" disabled={!files?.length || upload.isPending} onClick={() => upload.mutate()}>
              <Icon name="upload" />{upload.isPending ? "Enviando…" : "Enviar arquivos"}</button>
          </>
        )}
      </div>
      {isEngineer
        ? <DecisionForm r={r} itemComments={[]} setItemComments={() => undefined} onDone={onDone} />
        : <div className="card"><Hint>O envio do material cabe ao responsável pelos requisitos.</Hint></div>}
    </div>
  );
}

function History({ r }: { r: HitlDetail }) {
  const decisions = r.respostas.filter((x) => !POSITIONS.some((p) => p.id === x.decision));
  if (!decisions.length) return null;
  return (
    <div className="stack tight small">
      <strong>Decisões anteriores</strong>
      {decisions.map((x) => <div key={x.id} className="muted">{fmtDate(x.created_at)} · {decisionLabel(x.decision)} {x.comentario && `— ${x.comentario}`}</div>)}
    </div>
  );
}

function DraftPreview({ runId }: { runId: string }) {
  const doc = useQuery({ queryKey: ["artifacts", runId, "doc"], queryFn: () => api.get<string>(`/runs/${runId}/document`) });
  return doc.data ? (
    <div className="stack">
      <Hint>Assim vai ficar o documento. Para corrigir algo, abra a parte no menu à esquerda e clique em Editar esta parte.</Hint>
      <Markdown>{doc.data}</Markdown>
    </div>
  ) : <Loading what="Montando o documento" />;
}
