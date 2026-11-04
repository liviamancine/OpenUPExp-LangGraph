import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";
import Icon, { Logo } from "../components/Icon";
import { ErrorBox, PHASES } from "../components/ui";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ access_token: string }>("/auth/login", { email, password });
      setToken(r.access_token);
      navigate("/");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-hero">
        <Logo size={72} />
        <div>
          <h1>OpenUP<span style={{ color: "#a7f3d0" }}>Exp</span></h1>
          <p>Descubra, junto com a sua equipe, o que um sistema de IA precisa explicar — e para quem. A IA faz o
            trabalho pesado; as decisões continuam com vocês.</p>
        </div>
        <div className="login-steps">
          {Object.entries(PHASES).map(([id, p]) => (
            <div key={id}><Icon name={p.icon} size={20} />{id}. {p.titulo}</div>
          ))}
        </div>
      </section>
      <section className="login-form">
        <form className="card stack" onSubmit={submit}>
          <div>
            <h2 style={{ fontSize: 22 }}>Entrar</h2>
            <div className="muted small">Use o e-mail e a senha que você recebeu.</div>
          </div>
          <label>E-mail<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
            autoComplete="username" /></label>
          <label>Senha<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            autoComplete="current-password" /></label>
          <ErrorBox error={error} />
          <button className="primary big" disabled={busy}>{busy ? "Entrando…" : "Entrar"}<Icon name="arrowRight" /></button>
        </form>
      </section>
    </div>
  );
}
