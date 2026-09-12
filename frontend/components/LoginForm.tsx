"use client";

import { FormEvent, useState } from "react";
import { supabase } from "../lib/supabase";

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const result = await supabase!.auth.signInWithPassword({ email, password });
    if (result.error) setError(result.error.message);
    setBusy(false);
  }

  return <main className="auth-shell"><form className="login-card" onSubmit={submit}><p className="eyebrow">SALES INTELLIGENCE</p><h1>Sign in</h1><p className="muted">Use your Supabase account to access prospect data.</p><label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" required /></label><label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" required /></label>{error && <div className="error">{error}</div>}<button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form></main>;
}
