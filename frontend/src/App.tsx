import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, getToken, setToken } from "./api/client";
import type { HitlRequest, User } from "./api/types";
import LoginPage from "./pages/LoginPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectPage from "./pages/ProjectPage";
import RunPage from "./pages/RunPage";
import ReviewPage from "./pages/ReviewPage";
import InboxPage from "./pages/InboxPage";
import ArtifactPage from "./pages/ArtifactPage";

function TopBar() {
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.get<User>("/auth/me") });
  const inbox = useQuery({
    queryKey: ["inbox", "open"], queryFn: () => api.get<HitlRequest[]>("/hitl?status=open"), refetchInterval: 15000,
  });
  const pending = inbox.data?.length ?? 0;
  return (
    <header className="topbar">
      <Link to="/" className="brand">OpenUPExp</Link>
      <nav>
        <Link to="/">Projetos</Link>
        <Link to="/decisoes">Central de decisões {pending > 0 && <span className="badge-count">{pending}</span>}</Link>
      </nav>
      <span className="muted small">{me.data?.nome}</span>
      <button onClick={() => { setToken(null); navigate("/login"); }}>Sair</button>
    </header>
  );
}

export default function App() {
  const location = useLocation();
  if (!getToken() && location.pathname !== "/login") return <Navigate to="/login" replace />;
  if (location.pathname === "/login") return <LoginPage />;
  return (
    <div className="app">
      <TopBar />
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
