import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { ErrorBox, Loading, fmtDate } from "../components/ui";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get<Project[]>("/projects") });
  const [nome, setNome] = useState("");
  const [dominio, setDominio] = useState("");
  const create = useMutation({
    mutationFn: () => api.post<Project>("/projects", { nome, dominio: dominio || null }),
    onSuccess: (p) => navigate(`/projetos/${p.id}`),
  });

  return (
    <div className="stack">
      <div>
        <h1>Projetos</h1>
        <div className="muted">Cada projeto tem um escopo, uma base de referência e execuções do processo OpenUPExp.</div>
      </div>
      <div className="split">
        <div className="card">
          {projects.isLoading ? <Loading /> : (
            <table>
              <thead><tr><th>Projeto</th><th>Domínio</th><th>Criado em</th></tr></thead>
              <tbody>
                {projects.data?.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/projetos/${p.id}`}>{p.nome}</Link></td>
                    <td>{p.dominio ?? "—"}</td>
                    <td className="muted">{fmtDate(p.created_at)}</td>
                  </tr>
                ))}
                {projects.data?.length === 0 && <tr><td colSpan={3} className="muted">Nenhum projeto ainda.</td></tr>}
              </tbody>
            </table>
          )}
          <ErrorBox error={projects.error} />
        </div>
        <form className="card stack" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <h2>Novo projeto</h2>
          <label>Nome<input value={nome} onChange={(e) => setNome(e.target.value)} required /></label>
          <label>Domínio<input value={dominio} onChange={(e) => setDominio(e.target.value)} placeholder="opcional" /></label>
          <ErrorBox error={create.error} />
          <button className="primary" disabled={create.isPending}>Criar</button>
        </form>
      </div>
    </div>
  );
}
