import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { HitlRequest } from "../api/types";
import { ErrorBox, Loading, Status, Tabs, fmtDate } from "../components/ui";

export default function InboxPage() {
  const [status, setStatus] = useState<"open" | "decided">("open");
  const inbox = useQuery({ queryKey: ["inbox", status], queryFn: () => api.get<HitlRequest[]>(`/hitl?status=${status}`) });
  return (
    <div className="stack">
      <div>
        <h1>Central de decisões</h1>
        <div className="muted">Aprovações dos gateways, rodadas de consenso e pedidos de material de elicitação.</div>
      </div>
      <Tabs value={status} onChange={setStatus} items={[{ id: "open", label: "Pendentes" }, { id: "decided", label: "Decididas" }]} />
      <div className="card">
        {inbox.isLoading ? <Loading /> : (
          <table>
            <thead><tr><th>Tipo</th><th>Gateway</th><th>Projeto</th><th>Iteração</th><th>Aberta em</th><th>Status</th></tr></thead>
            <tbody>
              {inbox.data?.map((r) => (
                <tr key={r.id}>
                  <td><Status value={r.kind} /></td>
                  <td><Link to={`/decisoes/${r.id}`}>{r.payload.name ?? r.task_id}</Link></td>
                  <td>{r.projeto?.nome}</td><td>{r.iteracao}{r.iteracao >= 5 && <span className="badge warn">muitas iterações</span>}</td>
                  <td className="muted">{fmtDate(r.created_at)}</td><td><Status value={r.status} /></td>
                </tr>
              ))}
              {inbox.data?.length === 0 && <tr><td colSpan={6} className="muted">Nada por aqui.</td></tr>}
            </tbody>
          </table>
        )}
        <ErrorBox error={inbox.error} />
      </div>
    </div>
  );
}
