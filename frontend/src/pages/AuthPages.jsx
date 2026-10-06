import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Field, Spinner } from "../components/common";
import Logo from "../components/Logo";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../utils/format";

function Shell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden flex-col justify-between bg-panel p-12 lg:flex">
        <Logo size={32} />
        <div className="max-w-md">
          <h2 className="text-4xl font-semibold leading-tight">What should your home's electricity use look like right now?</h2>
          <p className="mt-4 text-mute">Stima Insight learns your household's normal pattern from its own history, forecasts what comes next, and tells you when today stops looking like you.</p>
        </div>
        <p className="text-xs text-faint">Final-year project: machine-learning electricity forecasting and anomaly detection for Kenyan households.</p>
      </section>
      <section className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mb-6 mt-1 text-sm text-mute">{subtitle}</p>
          {children}
          <div className="mt-6 text-sm text-mute">{footer}</div>
        </div>
      </section>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await login(form.email, form.password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Could not log in."));
    } finally { setBusy(false); }
  }

  return (
    <Shell title="Log in" subtitle="Welcome back." footer={<>New here? <Link className="text-amber underline-offset-2 hover:underline" to="/register">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Email"><input id="email" type="email" autoComplete="email" required className="field" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Password"><input id="password" type="password" autoComplete="current-password" required className="field" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        {error && <p role="alert" className="rounded-lg bg-sev-high/10 px-3 py-2 text-sm text-sev-high">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />} Log in</button>
      </form>
      <div className="mt-6 rounded-lg border border-dashed border-line p-3 text-xs text-mute">
        <p className="font-medium text-ink">Development demo account</p>
        <p className="mt-1">Created by <code>seed_database.py</code> for local use only.</p>
        <button type="button" className="mt-2 text-amber hover:underline" onClick={() => setForm({ email: "demo@example.com", password: "ChangeMe123!" })}>Fill demo login</button>
      </div>
    </Shell>
  );
}

export function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await register(form.name, form.email, form.password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Could not create the account."));
    } finally { setBusy(false); }
  }

  return (
    <Shell title="Create your account" subtitle="You'll set up your household next." footer={<>Already registered? <Link className="text-amber underline-offset-2 hover:underline" to="/login">Log in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Full name"><input id="name" required minLength={2} autoComplete="name" className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Email"><input id="email" type="email" required autoComplete="email" className="field" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Password" hint="At least 8 characters."><input id="password" type="password" required minLength={8} autoComplete="new-password" className="field" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        {error && <p role="alert" className="rounded-lg bg-sev-high/10 px-3 py-2 text-sm text-sev-high">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />} Create account</button>
      </form>
    </Shell>
  );
}
