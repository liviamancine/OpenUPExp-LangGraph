import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Diff, VersionDetail } from "../api/types";
import ArtifactView from "../components/ArtifactView";
import { ErrorBox, Loading, Status, fmtDate, show } from "../components/ui";

export default function ArtifactPage() {
  const { versionId = "" } = useParams();
  const navigate = useNavigate();
  const v = useQuery({ queryKey: ["version", versionId], queryFn: () => api.get<VersionDetail>(`/artifact-versions/${versionId}`) });
  const [compare, setCompare] = useState<string>("");
  const diff = useQuery({
    queryKey: ["diff", versionId, compare], enabled: !!compare,
    queryFn: () => api.get<Diff>(`/artifact-versions/${versionId}/diff/${compare}`),
  });
  if (v.isLoading) return <Loading />;
  if (!v.data) return <ErrorBox error={v.error} />;
  const d = v.data;
  return (
    <div className="stack">
      <div className="small"><Link to={`/execucoes/${d.run_id}`}>← execução</Link></div>
      <div className="split">
        <div className="card"><ArtifactView versionId={versionId} onNewVersion={(id) => navigate(`/versoes/${id}`)} /></div>
        <div className="stack">
          <div className="card stack">
            <h2>Histórico</h2>
            <table className="small">
              <tbody>
                {d.historico.map((h) => (
                  <tr key={h.id} className={`list-item ${h.id === versionId ? "active" : ""}`}>
                    <td><Link to={`/versoes/${h.id}`}>v{h.version_no}</Link></td>
                    <td><Status value={h.status} /></td><td><Status value={h.origin} /></td>
                    <td>it{h.iteracao}</td><td className="muted">{fmtDate(h.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <label>Comparar com
              <select value={compare} onChange={(e) => setCompare(e.target.value)}>
                <option value="">—</option>
                {d.historico.filter((h) => h.id !== versionId).map((h) => <option key={h.id} value={h.id}>v{h.version_no} ({h.origin})</option>)}
              </select>
            </label>
            {diff.data && <DiffView diff={diff.data} />}
          </div>
          <div className="card stack">
            <h2>Proveniência</h2>
            <div className="muted small">Versões que o agente efetivamente recebeu como entrada.</div>
            {d.dependencias.length === 0 && <div className="muted">Sem dependências registradas.</div>}
            {d.dependencias.map((dep) => (
              <div key={dep.version_id} className="row small">
                <Link to={`/versoes/${dep.version_id}`} className="mono">{dep.artifact}</Link>
                <span>v{dep.version_no}</span><Status value={dep.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function DiffView({ diff }: { diff: Diff }) {
  const nothing = !diff.campos.length && !diff.adicionados?.length && !diff.removidos?.length && !diff.alterados?.length;
  if (nothing) return <div className="muted small">Sem diferenças.</div>;
  return (
    <div className="stack small">
      {diff.adicionados?.map((i) => <div key={String(i.id)} className="diff-new">+ {String(i.id)} {show(Object.values(i)[1])}</div>)}
      {diff.removidos?.map((i) => <div key={String(i.id)} className="diff-old">− {String(i.id)} {show(Object.values(i)[1])}</div>)}
      {diff.alterados?.map((a) => (
        <div key={a.id}>
          <strong>{a.id}</strong>
          {a.campos.map((c) => (
            <div key={c.campo}><span className="muted">{c.campo}:</span> <span className="diff-old">{show(c.antes)}</span> → <span className="diff-new">{show(c.depois)}</span></div>
          ))}
        </div>
      ))}
      {diff.campos.map((c) => (
        <div key={c.campo}><span className="muted">{c.campo}:</span> <span className="diff-old">{show(c.antes)}</span> → <span className="diff-new">{show(c.depois)}</span></div>
      ))}
    </div>
  );
}
