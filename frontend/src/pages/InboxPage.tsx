import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { HitlRequest } from "../api/types";
import Icon, { type IconName } from "../components/Icon";
import { Empty, ErrorBox, Loading, PhaseChip, Status, Tabs, fmtDate } from "../components/ui";

const KIND: Record<string, { title: string; text: string; icon: IconName }> = {
  approval: { title: "Revisar e aprovar", text: "A IA terminou uma etapa e precisa da sua aprovação.", icon: "checkCircle" },
  consensus: { title: "Dar sua opinião", text: "A equipe está avaliando um resultado. Diga se concorda.", icon: "thumbsUp" },
  input: { title: "Enviar material das conversas", text: "Envie as transcrições ou anotações das entrevistas.", icon: "upload" },
};

export default function InboxPage() {
  const [status, setStatus] = useState<"open" | "decided">("open");
  const inbox = useQuery({ queryKey: ["inbox", status], queryFn: () => api.get<HitlRequest[]>(`/hitl?status=${status}`) });
  return (
    <div className="stack">
      <div className="page-head">
        <div className="grow">
          <h1>O que precisa de mim</h1>
          <div className="subtitle">Momentos em que a IA para e espera por pessoas: aprovar uma etapa, dar opinião
            ou enviar material.</div>
        </div>
      </div>
      <Tabs value={status} onChange={setStatus} items={[
        { id: "open", label: "Pendentes", icon: "bell" }, { id: "decided", label: "Já resolvidas", icon: "check" },
      ]} />
      {inbox.isLoading ? <Loading /> : (
        <div className="stack tight">
          {inbox.data?.map((r) => {
            const k = KIND[r.kind] ?? KIND.approval;
            const phase = r.payload.phase ?? r.task_id.split(".")[0];
            return (
              <Link key={r.id} to={`/decisoes/${r.id}`} className="task-row">
                <span className={`kind-icon ${r.kind}`}><Icon name={k.icon} size={20} /></span>
                <span className="grow">
                  <div className="strong">{k.title} <span className="muted small">· {r.projeto?.nome}</span></div>
                  <div className="muted small">{k.text}</div>
                  <div className="row tiny muted" style={{ marginTop: 4, gap: 8 }}>
                    <PhaseChip phase={phase} /><span>{r.payload.name ?? r.task_id}</span>
                    {r.iteracao > 1 && <span>· {r.iteracao}ª rodada</span>}<span>· desde {fmtDate(r.created_at)}</span>
                  </div>
                </span>
                {status === "open" ? <span className="btn primary small">Abrir<Icon name="arrowRight" size={14} /></span> : <Status value={r.status} />}
              </Link>
            );
          })}
          {inbox.data?.length === 0 && (
            <div className="card"><Empty icon={status === "open" ? "checkCircle" : "clock"}>
              {status === "open" ? "Tudo em dia! Nada esperando por você." : "Nenhuma decisão registrada ainda."}</Empty></div>
          )}
        </div>
      )}
      <ErrorBox error={inbox.error} />
    </div>
  );
}
