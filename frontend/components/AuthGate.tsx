"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import LoginForm from "./LoginForm";

type AuthContextValue = { session: Session | null; signOut: () => Promise<void> };
const AuthContext = createContext<AuthContextValue>({ session: null, signOut: async () => {} });

export function useAuth() { return useContext(AuthContext); }

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session); syncToken(data.session); setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession); syncToken(nextSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  async function signOut() {
    if (supabase) await supabase.auth.signOut();
    localStorage.removeItem("sales_intelligence_access_token");
  }

  if (loading) return <div className="auth-loading">Loading session…</div>;
  if (!supabase && process.env.NEXT_PUBLIC_LOCAL_DEMO === "true") {
    return <AuthContext.Provider value={{ session: null, signOut: async () => {} }}>{children}</AuthContext.Provider>;
  }
  if (!supabase) return <div className="auth-loading"><h2>Supabase is not configured</h2><p>Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, or enable NEXT_PUBLIC_LOCAL_DEMO=true for local testing.</p></div>;
  return <AuthContext.Provider value={{ session, signOut }}>{session ? children : <LoginForm />}</AuthContext.Provider>;
}

function syncToken(session: Session | null) {
  if (typeof window === "undefined") return;
  if (session?.access_token) localStorage.setItem("sales_intelligence_access_token", session.access_token);
  else localStorage.removeItem("sales_intelligence_access_token");
}
