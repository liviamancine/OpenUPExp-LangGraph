import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { LlmProfile, ProjectDetail, RunSummary, User } from "../api/types";
import Icon, { type IconName } from "../components/Icon";
import { Empty, ErrorBox, Hint, Loading, PHASES, PhaseChip, ROLE_LABEL, Status, Tabs, fmtDate } from "../components/ui";

const KINDS: { id: string; label: string; help: string; icon: IconName }[] = [
  { id: "escopo", label: "Escopo do projeto", help: "Obrigatório. Descreve o sistema e o problema.", icon: "file" },
  { id: "lei", label: "Lei ou norma", help: "A IA cita os artigos ao propor requisitos.", icon: "book" },
  { id: "manual", label: "Manual ou procedimento", help: "Regras internas do domínio.", icon: "book" },
  { id: "academico", label: "Artigo ou literatura", help: "Base para os tipos de explicação.", icon: "book" },
  { id: "elicitacao", label: "Entrevistas e reuniões", help: "Transcrições e anotações (etapa 2).", icon: "chat" },
];
const KIND_LABEL = Object.fromEntries(KINDS.map((k) => [k.id, k.label]));

const STRATEGIES = [
  { id: "D", label: "Equilibrada (recomendada)", help: "Entrega à IA só o necessário de cada tarefa, com resumos das etapas anteriores." },
  { id: "C", label: "Estruturada", help: "Só os dados estruturados das etapas anteriores." },
  { id: "A", label: "Tudo", help: "O documento inteiro a cada tarefa. Mais caro; útil para comparação." },
];

type StepState = "done" | "running" | "waiting" | "failed" | "available" | "locked";

const STATE_INFO: Record<StepState, { label: string; icon: IconName }> = {
  done: { label: "Concluída e aprovada", icon: "checkCircle" },
  running: { label: "A IA está trabalhando", icon: "clock" },
  waiting: { label: "Aguardando uma decisão", icon: "bell" },
  failed: { label: "Parou com erro", icon: "xCircle" },
  available: { label: "Pronta para começar", icon: "play" },
  locked: { label: "Ainda não disponível", icon: "lock" },
};

export default function ProjectPage() {
  const { projectId = "" } = useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"etapas" | "documentos" | "equipe">("etapas");
  const project = useQuery({
    queryKey: ["project", projectId], queryFn: () => api.get<ProjectDetail>(`/projects/${projectId}`),
    refetchInterval: (q) => (q.state.data?.corpora.some((c) => c.status === "building") ? 3000 : false),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["project", projectId] });

  if (project.isLoading) return <Loading what="Carregando o projeto" />;
  if (!project.data) return <ErrorBox error={project.error} />;
  const p = project.data;
  const isEngineer = p.meu_papel === "requirements_engineer" || p.meu_papel === "admin";

  return (
    <div className="stack">
      <div>
        <Link to="/" className="back"><Icon name="arrowLeft" size={14} />Meus projetos</Link>
        <div className="page-head">
          <div className="grow">
            <h1>{p.nome}</h1>
            <div className="subtitle">{p.dominio ?? "Área não informada"} · você participa como <strong>{ROLE_LABEL[p.meu_papel] ?? p.meu_papel}</strong></div>
          </div>
        </div>
      </div>
      <Tabs value={tab} onChange={setTab} items={[
        { id: "etapas", label: "Etapas", icon: "map" },
        { id: "documentos", label: `Documentos (${p.fontes.filter((f) => f.ativo).length})`, icon: "book" },
        { id: "equipe", label: `Equipe (${p.membros.length})`, icon: "users" },
      ]} />
      {tab === "etapas" && <Journey project={p} isEngineer={isEngineer} goTo={setTab} />}
      {tab === "documentos" && <Documents project={p} isEngineer={isEngineer} onChange={refresh} />}
      {tab === "equipe" && <Members project={p} canEdit={isEngineer} onChange={refresh} />}
    </div>
  );
}

function stepState(phase: string, runs: RunSummary[], previousDone: boolean, hasScope: boolean): StepState {
  const latest = runs[0];
  if (latest?.status === "running" || latest?.status === "queued") return "running";
  if (latest?.status === "waiting_human") return "waiting";
  if (latest?.status === "failed") return "failed";
  if (runs.some((r) => r.status === "completed")) return "done";
  return previousDone && (phase !== "1" || hasScope) ? "available" : "locked";
}

function Journey({ project: p, isEngineer, goTo }: {
  project: ProjectDetail; isEngineer: boolean; goTo: (t: "documentos" | "equipe") => void;
}) {
  const navigate = useNavigate();
  const profiles = useQuery({ queryKey: ["llm-profiles"], queryFn: () => api.get<LlmProfile[]>("/llm/profiles") });
  const [choice, setChoice] = useState<string | null>(null);  // id do perfil ou "fake"
  const [strategy, setStrategy] = useState("D");
  const usable = profiles.data?.filter((x) => x.disponivel) ?? [];
  const selected = choice ?? (usable.find((x) => x.padrao) ?? usable[0])?.id ?? "fake";
  const gateway = selected === "fake" ? "fake" : "baml";
  const start = useMutation({
    mutationFn: ({ phase, base }: { phase: string; base: string | null }) => api.post<RunSummary>(
      `/projects/${p.id}/runs`, { phase, context_strategy: strategy, agent_gateway: gateway, base_run_id: base,
        llm_profile_id: gateway === "baml" ? selected : null }),
    onSuccess: (r) => navigate(`/execucoes/${r.id}`),
  });

  const byPhase = (ph: string) => p.execucoes.filter((r) => r.phase === ph)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const lastDone = (ph: string) => byPhase(ph).find((r) => r.status === "completed");
  const hasScope = p.fontes.some((f) => f.source_kind === "escopo" && f.ativo);
  const ready = p.corpora.some((c) => c.status === "ready");
  const elicitationDocs = p.fontes.filter((f) => f.source_kind === "elicitacao" && f.ativo).length;

  return (
    <div className="stack">
      <div className="journey">
        {Object.entries(PHASES).map(([id, info]) => {
          const runs = byPhase(id);
          const previous = id === "1" ? null : lastDone(String(Number(id) - 1));
          const state = stepState(id, runs, id === "1" || !!previous, hasScope);
          const latest = runs[0];
          const st = STATE_INFO[state];
          const begin = () => start.mutate({ phase: id, base: previous?.id ?? null });
          return (
            <div key={id} className={`step p${id} ${state}`}>
              <div className="step-top">
                <span className="phase-icon"><Icon name={info.icon} size={22} /></span>
                <span><div className="step-num">Etapa {id} · {info.nome}</div><div className="step-title">{info.titulo}</div></span>
              </div>
              <div className="step-desc">{info.descricao}</div>
              <div className={`state ${state}`}><Icon name={st.icon} size={16} />{st.label}</div>
              {state === "locked" && <div className="muted small">
                {id === "1" ? "Envie o documento de escopo do projeto primeiro." : `Conclua a etapa ${Number(id) - 1} primeiro.`}</div>}
              {id === "2" && state === "available" && <div className="muted small">
                A plataforma vai pedir o material das conversas com as pessoas{elicitationDocs ? ` (${elicitationDocs} já enviado)` : ""}.</div>}
              <div className="step-actions">
                {state === "waiting" && latest && <Link to={`/execucoes/${latest.id}`} className="btn primary"><Icon name="bell" />Responder agora</Link>}
                {(state === "running" || state === "failed") && latest && <Link to={`/execucoes/${latest.id}`} className="btn primary">
                  <Icon name="arrowRight" />Acompanhar</Link>}
                {state === "available" && isEngineer && <button className="primary" onClick={begin} disabled={start.isPending}>
                  <Icon name="play" />Começar</button>}
                {state === "done" && lastDone(id) && <Link to={`/execucoes/${lastDone(id)!.id}`} className="btn"><Icon name="file" />Ver resultado</Link>}
                {state === "done" && isEngineer && <button className="ghost" onClick={begin} disabled={start.isPending}
                  title="Faz a etapa de novo, a partir do resultado aprovado da etapa anterior"><Icon name="redo" />Refazer</button>}
              </div>
            </div>
          );
        })}
      </div>
      <ErrorBox error={start.error} />

      <div className="grid-2">
        <div className="card stack">
          <div className="card-head"><span className="icon-bubble"><Icon name="checkCircle" /></span><h2>Antes de começar</h2></div>
          <div className="checklist">
            <div className={`check-item ${hasScope ? "ok" : "todo"}`}><Icon name={hasScope ? "checkCircle" : "alert"} />
              <span><strong>Documento de escopo</strong> — {hasScope ? "enviado." : <>necessário para a etapa 1. <a href="#" onClick={(e) => { e.preventDefault(); goTo("documentos"); }}>Enviar agora</a></>}</span></div>
            <div className={`check-item ${ready ? "ok" : "optional"}`}><Icon name={ready ? "checkCircle" : "info"} />
              <span><strong>Leis, manuais e artigos</strong> — {ready ? "prontos para a IA consultar." : <>recomendado: sem eles, a IA não consegue citar fontes. <a href="#" onClick={(e) => { e.preventDefault(); goTo("documentos"); }}>Adicionar</a></>}</span></div>
            <div className={`check-item ${p.membros.length > 1 ? "ok" : "optional"}`}><Icon name={p.membros.length > 1 ? "checkCircle" : "info"} />
              <span><strong>Equipe</strong> — {p.membros.length > 1 ? `${p.membros.length} pessoas.` : <>convide quem vai opinar nas etapas 2 a 4. <a href="#" onClick={(e) => { e.preventDefault(); goTo("equipe"); }}>Convidar</a></>}</span></div>
          </div>
        </div>
        {isEngineer && (
          <div className="card stack">
            <div className="card-head"><span className="icon-bubble"><Icon name="settings" /></span><h2>Como a IA vai trabalhar</h2></div>
            <div className="small muted">Qual modelo de IA vai executar as próximas etapas:</div>
            <div className="choices">
              {profiles.data?.map((x) => (
                <label key={x.id} className={`choice ${selected === x.id ? "selected" : ""}`}
                  style={x.disponivel ? undefined : { opacity: 0.55, cursor: "not-allowed" }}>
                  <input type="radio" name="gw" checked={selected === x.id} disabled={!x.disponivel} onChange={() => setChoice(x.id)} />
                  <span className="grow">
                    <div className="title row" style={{ gap: 6 }}>
                      <Icon name={x.modelo.local ? "lock" : "sparkles"} size={15} />{x.nome}
                      {x.padrao && <span className="badge ok">padrão</span>}
                      {x.modelo.local && <span className="badge">no seu computador</span>}
                    </div>
                    <div className="help">{x.modelo.local
                      ? x.disponivel
                        ? "Modelo de referência, sem enviar documentos para fora. Na CPU é lento: uma etapa pode levar bastante tempo."
                        : "Desligado nesta instalação (opcional, pesado sem placa de vídeo)."
                      : x.disponivel ? (x.modelo.descricao ?? `${x.modelo.provider} · ${x.modelo.model}`) : "Sem chave configurada no servidor."}</div>
                  </span>
                </label>
              ))}
              <label className={`choice ${selected === "fake" ? "selected" : ""}`}>
                <input type="radio" name="gw" checked={selected === "fake"} onChange={() => setChoice("fake")} />
                <span><div className="title"><Icon name="zap" size={15} /> Modo de teste</div><div className="help">Respostas simuladas, sem IA e sem custo — para conhecer o processo.</div></span>
              </label>
            </div>
            <ErrorBox error={profiles.error} />
            <details className="advanced">
              <summary>Opções avançadas</summary>
              <div className="stack tight">
                <div className="small muted">Quanto do histórico do projeto a IA recebe em cada tarefa:</div>
                <div className="choices">
                  {STRATEGIES.map((s) => (
                    <label key={s.id} className={`choice ${strategy === s.id ? "selected" : ""}`}>
                      <input type="radio" name="st" checked={strategy === s.id} onChange={() => setStrategy(s.id)} />
                      <span><div className="title">{s.label}</div><div className="help">{s.help}</div></span>
                    </label>
                  ))}
                </div>
              </div>
            </details>
          </div>
        )}
      </div>

      <History runs={p.execucoes} />
    </div>
  );
}

function History({ runs }: { runs: RunSummary[] }) {
  return (
    <details className="card">
      <summary><strong>Histórico de execuções</strong> <span className="muted small">({runs.length})</span></summary>
      {runs.length === 0 ? <Empty icon="clock">Nenhuma execução ainda.</Empty> : (
        <table style={{ marginTop: 10 }}>
          <thead><tr><th>Etapa</th><th>Situação</th><th>Modo</th><th>Iniciada</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td><PhaseChip phase={r.phase} /></td>
                <td><Status value={r.status} /></td>
                <td className="small">{r.agent_gateway === "fake" ? "teste" : "IA"}</td>
                <td className="muted small">{fmtDate(r.created_at)}</td>
                <td><Link to={`/execucoes/${r.id}`}>Abrir</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

function Documents({ project: p, isEngineer, onChange }: { project: ProjectDetail; isEngineer: boolean; onChange: () => void }) {
  const [kind, setKind] = useState("escopo");
  const [files, setFiles] = useState<FileList | null>(null);
  const upload = useMutation({
    mutationFn: async () => {
      for (const f of Array.from(files ?? [])) {
        const form = new FormData();
        form.append("file", f);
        form.append("source_kind", kind);
        await api.upload(`/projects/${p.id}/sources`, form);
      }
    },
    onSuccess: () => { setFiles(null); onChange(); },
  });
  const index = useMutation({ mutationFn: () => api.post(`/projects/${p.id}/corpus`), onSuccess: () => setTimeout(onChange, 1500) });
  const deactivate = useMutation({ mutationFn: (id: string) => api.del(`/projects/${p.id}/sources/${id}`), onSuccess: onChange });
  const building = p.corpora.some((c) => c.status === "building");
  const latest = p.corpora[0];
  const active = p.fontes.filter((f) => f.ativo);

  return (
    <div className="split">
      <div className="stack">
        <div className="card">
          <div className="card-head"><span className="icon-bubble"><Icon name="book" /></span><h2 className="grow">Documentos do projeto</h2></div>
          {active.length === 0 ? <Empty icon="upload">Nenhum documento. Comece pelo escopo do projeto.</Empty> : (
            <table>
              <thead><tr><th>Arquivo</th><th>Tipo</th><th>Páginas</th><th></th></tr></thead>
              <tbody>
                {active.map((f) => (
                  <tr key={f.id}>
                    <td><span className="row" style={{ gap: 8, flexWrap: "nowrap" }}><Icon name="file" size={16} />{f.arquivo}</span></td>
                    <td><span className="badge">{KIND_LABEL[f.source_kind] ?? f.source_kind}</span></td>
                    <td>{f.paginas ?? "—"}{Number(f.meta?.paginas_vazias ?? 0) > 0 &&
                      <> <span className="badge warn" title="páginas sem texto (talvez imagem escaneada)">{String(f.meta.paginas_vazias)} sem texto</span></>}</td>
                    <td>{isEngineer && <button className="ghost small" onClick={() => deactivate.mutate(f.id)} title="Deixa de ser usado pela IA">
                      <Icon name="archive" size={14} />Desativar</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="card stack">
          <div className="card-head"><span className="icon-bubble"><Icon name="search" /></span>
            <span className="grow"><h2>Consulta da IA</h2>
              <div className="muted small">Para que a IA possa citar leis, manuais e artigos, os documentos precisam ser preparados para busca.</div></span>
          </div>
          {building ? <Loading what="Preparando os documentos" />
            : latest ? <Hint tone={latest.status === "ready" ? "ok" : "warn"} icon={latest.status === "ready" ? "checkCircle" : "alert"}>
              Última preparação em {fmtDate(latest.created_at)}: <Status value={latest.status} /> · {latest.stats?.chunks ?? 0} trechos.
              Se você adicionou documentos depois disso, prepare de novo.</Hint>
              : <Hint tone="warn" icon="alert">Os documentos de consulta ainda não foram preparados.</Hint>}
          {isEngineer && <button onClick={() => index.mutate()} disabled={index.isPending || building}>
            <Icon name="redo" />Preparar documentos para consulta</button>}
          <ErrorBox error={index.error} />
          <div className="muted small">As entrevistas da etapa 2 são preparadas automaticamente quando você as envia.</div>
          {p.corpora.length > 0 && (
            <details className="advanced">
              <summary>Detalhes técnicos</summary>
              <table className="small">
                <thead><tr><th>Quando</th><th>Situação</th><th>Modelo</th><th>Trechos</th><th>Reaproveitados</th></tr></thead>
                <tbody>
                  {p.corpora.map((c) => (
                    <tr key={c.id}><td>{fmtDate(c.created_at)}</td><td><Status value={c.status} /></td>
                      <td>{c.embedding_provider} · {c.embedding_model}</td><td>{c.stats?.chunks ?? "—"}</td>
                      <td>{c.stats?.embeddings_reaproveitados ?? "—"}</td></tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      </div>
      {isEngineer && (
        <div className="card stack">
          <div className="card-head"><span className="icon-bubble"><Icon name="upload" /></span><h2>Enviar documentos</h2></div>
          <div className="choices">
            {KINDS.map((k) => (
              <label key={k.id} className={`choice ${kind === k.id ? "selected" : ""}`}>
                <input type="radio" name="kind" checked={kind === k.id} onChange={() => setKind(k.id)} />
                <span><div className="title">{k.label}</div><div className="help">{k.help}</div></span>
              </label>
            ))}
          </div>
          <input type="file" multiple accept=".pdf,.txt,.md" onChange={(e) => setFiles(e.target.files)} />
          <div className="muted tiny">PDF, TXT ou Markdown.</div>
          <ErrorBox error={upload.error} />
          <button className="primary" disabled={!files?.length || upload.isPending} onClick={() => upload.mutate()}>
            <Icon name="upload" />{upload.isPending ? "Enviando…" : "Enviar"}</button>
        </div>
      )}
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
  const roles = [
    { id: "requirements_engineer", help: "Inicia as etapas, aprova e decide o que refazer." },
    { id: "participant", help: "Dá opinião nas rodadas de consenso." },
    { id: "observer", help: "Só visualiza." },
    { id: "researcher", help: "Acompanha os experimentos." },
  ];
  return (
    <div className="split">
      <div className="card">
        <div className="card-head"><span className="icon-bubble"><Icon name="users" /></span><h2>Equipe</h2></div>
        <div className="stack tight">
          {project.membros.map((m) => (
            <div key={m.user.id} className="row" style={{ flexWrap: "nowrap" }}>
              <span className="avatar">{m.user.nome.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase()}</span>
              <span className="grow"><div className="strong">{m.user.nome}</div><div className="muted small">{m.user.email}</div></span>
              <span className="badge">{ROLE_LABEL[m.papel_plataforma] ?? m.papel_plataforma}</span>
              {m.papel_openupexp && <span className="badge">{m.papel_openupexp}</span>}
            </div>
          ))}
        </div>
      </div>
      {canEdit && (
        <form className="card stack" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <div className="card-head"><span className="icon-bubble"><Icon name="plus" /></span><h2>Adicionar pessoa</h2></div>
          <label>Pessoa<select value={userId} onChange={(e) => setUserId(e.target.value)} required>
            <option value="">Escolha…</option>
            {users.data?.map((u) => <option key={u.id} value={u.id}>{u.nome} ({u.email})</option>)}
          </select></label>
          <div className="choices">
            {roles.map((r) => (
              <label key={r.id} className={`choice ${role === r.id ? "selected" : ""}`}>
                <input type="radio" name="role" checked={role === r.id} onChange={() => setRole(r.id)} />
                <span><div className="title">{ROLE_LABEL[r.id]}</div><div className="help">{r.help}</div></span>
              </label>
            ))}
          </div>
          <label>Papel no processo (opcional)<input value={theory} onChange={(e) => setTheory(e.target.value)}
            placeholder="ex.: Especialista em Regulação" /></label>
          <ErrorBox error={add.error} />
          <button className="primary" disabled={!userId}>Adicionar</button>
        </form>
      )}
    </div>
  );
}
