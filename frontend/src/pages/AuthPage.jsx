import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ErrorNote, Field } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function AuthPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next")?.startsWith("/") ? params.get("next") : "/";

  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isLogin) await login(form.username.trim(), form.password);
      else await register({ ...form, username: form.username.trim() });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <div className="card p-8">
        <h1 className="text-2xl font-bold">{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {isLogin ? "Sign in to buy tickets or manage your events." : "Your tickets will be sent to your email."}
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <Field label="Username">
            <input className="input" value={form.username} onChange={set("username")} autoComplete="username" required />
          </Field>
          {!isLogin && (
            <Field label="Email">
              <input className="input" type="email" value={form.email} onChange={set("email")} autoComplete="email" required />
            </Field>
          )}
          <Field label="Password">
            <input
              className="input"
              type="password"
              value={form.password}
              onChange={set("password")}
              autoComplete={isLogin ? "current-password" : "new-password"}
              required
            />
          </Field>
          <ErrorNote>{error}</ErrorNote>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          {isLogin ? "New to Gatepass?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="font-medium text-brand-600 hover:underline"
            onClick={() => {
              setMode(isLogin ? "register" : "login");
              setError("");
            }}
          >
            {isLogin ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
      <p className="mt-4 text-center text-xs text-slate-400">
        Just looking around? Sign in as <strong>demo</strong> / <strong>Demo-pass-123</strong> to see the organizer tools.
      </p>
    </div>
  );
}
