import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, getToken, setToken } from "./api/client";
import type { HitlRequest, User } from "./api/types";
import Icon, { Logo } from "./components/Icon";
import LoginPage from "./pages/LoginPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectPage from "./pages/ProjectPage";
import RunPage from "./pages/RunPage";
import ReviewPage from "./pages/ReviewPage";
import InboxPage from "./pages/InboxPage";
import ArtifactPage from "./pages/ArtifactPage";

type Theme = "light" | "dark" | null;

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : null;
  } catch {
    return null;
  }
}

function useTheme(): [boolean, () => void] {
  const [theme, setTheme] = useState<Theme>(readTheme);
  const systemDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  const dark = theme ? theme === "dark" : systemDark;
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);
  const toggle = () => {
    const next = dark ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem("theme", next); } catch { /* sem armazenamento: vale só nesta sessão */ }
  };
  return [dark, toggle];
}

export function BrandMark() {
  return (
    <span className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
      <Logo size={38} />
      <span>
        <div className="brand-name">OpenUP<span>Exp</span></div>
        <div className="brand-sub">explicabilidade para IA</div>
      </span>
    </span>
  );
}

function Sidebar() {
  const navigate = useNavigate();
  const [dark, toggleTheme] = useTheme();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.get<User>("/auth/me") });
  const inbox = useQuery({
    queryKey: ["inbox", "open"], queryFn: () => api.get<HitlRequest[]>("/hitl?status=open"), refetchInterval: 15000,
  });
  const pending = inbox.data?.length ?? 0;
  const initials = (me.data?.nome ?? "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <aside className="sidebar">
      <NavLink to="/" className="brand" aria-label="OpenUPExp — início"><BrandMark /></NavLink>
      <nav className="nav">
        <div className="nav-label">Trabalho</div>
        <NavLink to="/" end><Icon name="folder" /><span className="text">Meus projetos</span></NavLink>
        <NavLink to="/decisoes">
          <Icon name="bell" /><span className="text">O que precisa de mim</span>
          {pending > 0 && <span className="count" aria-label={`${pending} pendentes`}>{pending}</span>}
        </NavLink>
      </nav>
      <div className="side-foot">
        <div className="side-user">
          <span className="avatar">{initials}</span>
          <span className="grow">
            <div className="name">{me.data?.nome ?? "—"}</div>
            <div className="tiny" style={{ color: "var(--side-text)" }}>{me.data?.email}</div>
          </span>
        </div>
        <button type="button" onClick={toggleTheme} title="Alternar tema claro/escuro">
          <Icon name={dark ? "sun" : "moon"} /><span className="text">{dark ? "Tema claro" : "Tema escuro"}</span>
        </button>
        <button type="button" onClick={() => { setToken(null); navigate("/login"); }}>
          <Icon name="logout" /><span className="text">Sair</span>
        </button>
      </div>
    </aside>
  );
}

export default function App() {
  const location = useLocation();
  if (!getToken() && location.pathname !== "/login") return <Navigate to="/login" replace />;
  if (location.pathname === "/login") return <LoginPage />;
  return (
    <div className="shell">
      <Sidebar />
      <main className="page">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projetos/:projectId" element={<ProjectPage />} />
          <Route path="/execucoes/:runId" element={<RunPage />} />
          <Route path="/decisoes" element={<InboxPage />} />
          <Route path="/decisoes/:requestId" element={<ReviewPage />} />
          <Route path="/versoes/:versionId" element={<ArtifactPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
