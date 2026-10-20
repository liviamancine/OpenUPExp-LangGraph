import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Project } from "../api/types";
import Icon from "../components/Icon";
import { Empty, ErrorBox, Loading, PHASES, fmtDate } from "../components/ui";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get<Project[]>("/projects") });
  const [creating, setCreating] = useState(false);
  const [nome, setNome] = useState("");
  const [dominio, setDominio] = useState("");
  const create = useMutation({
    mutationFn: () => api.post<Project>("/projects", { nome, dominio: dominio || null }),
    onSuccess: (p) => navigate(`/projetos/${p.id}`),
  });

  return (
    <div className="stack">
      <section className="hero">
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow">
            <h1>Meus projetos</h1>
            <div className="subtitle">Cada projeto passa por quatro etapas. Em cada uma, a IA prepara uma proposta e
              você, com a sua equipe, revisa e aprova.</div>
          </div>
          <button className="light big" onClick={() => setCreating(true)}><Icon name="plus" />Novo projeto</button>
        </div>
        <div className="hero-steps">
          {Object.entries(PHASES).map(([id, p]) => (
            <div key={id} className="hero-step">
              <span className="num"><Icon name={p.icon} size={18} /></span>
              <span><div className="strong">{id}. {p.titulo}</div><div className="small muted">{p.descricao}</div></span>
            </div>
          ))}
        </div>
      </section>

      {projects.isLoading ? <Loading what="Carregando projetos" /> : (
        <div className="cards">
          {creating && (
            <form className="tile tile-new stack" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
              <div className="tile-title">Novo projeto</div>
              <label>Nome do projeto<input value={nome} onChange={(e) => setNome(e.target.value)} required autoFocus
                placeholder="ex.: Sistema de análise de crédito" /></label>
              <label>Área (opcional)<input value={dominio} onChange={(e) => setDominio(e.target.value)}
                placeholder="ex.: saúde, finanças, serviço público" /></label>
              <ErrorBox error={create.error} />
              <div className="row">
                <button className="primary" disabled={create.isPending}>Criar projeto</button>
                <button type="button" className="ghost" onClick={() => setCreating(false)}>Cancelar</button>
              </div>
            </form>
          )}
          {projects.data?.map((p) => (
            <Link key={p.id} to={`/projetos/${p.id}`} className="tile">
              <div className="row" style={{ flexWrap: "nowrap" }}>
                <span className="phase-icon" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}><Icon name="folder" size={20} /></span>
                <span className="grow"><div className="tile-title">{p.nome}</div>
                  <div className="muted small">{p.dominio ?? "área não informada"}</div></span>
              </div>
              <div className="row muted small"><Icon name="clock" size={14} />criado em {fmtDate(p.created_at)}
                <span className="grow" /><span style={{ color: "var(--accent)", fontWeight: 700 }}>Abrir <Icon name="arrowRight" size={14} /></span></div>
            </Link>
          ))}
        </div>
      )}
      {projects.data?.length === 0 && !creating && (
        <div className="card"><Empty icon="folder">Você ainda não tem projetos. Clique em <strong>Novo projeto</strong> para começar.</Empty></div>
      )}
      <ErrorBox error={projects.error} />
    </div>
  );
}
