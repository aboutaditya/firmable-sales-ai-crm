"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useAuth } from "../components/AuthGate";
import Topbar from "../components/shared/Topbar";
import QueueBar from "../components/dashboard/QueueBar";
import AICard from "../components/dashboard/AICard";
import WorkflowCard from "../components/dashboard/WorkflowCard";
import LeadDetail from "../components/dashboard/LeadDetail";
import AdminModal from "../components/dashboard/AdminModal";
import { useNotices } from "../hooks/useNotices";
import { useQueueLead } from "../hooks/useQueueLead";
import { useAiAssist } from "../hooks/useAiAssist";
import { useAdminPanel } from "../hooks/useAdminPanel";
import { observedSignals } from "../lib/dispositions";

export default function Dashboard() {
  const { session, signOut } = useAuth();
  const isLocalDemo = !session && process.env.NEXT_PUBLIC_LOCAL_DEMO === "true";
  const appRoles = session?.user.app_metadata?.roles;
  const isAdmin = !!session && (session.user.app_metadata?.role === "admin" || session.user.user_metadata?.role === "admin" || (Array.isArray(appRoles) && appRoles.includes("admin")));
  const { error, notice, setError, setNotice } = useNotices();
  const queue = useQueueLead({ isAdmin, onError: setError, onNotice: setNotice });
  const ai = useAiAssist(setError);
  const admin = useAdminPanel({ isAdmin, authenticated: !!session, onError: setError, onNotice: setNotice });

  useEffect(() => { ai.resetAi(); }, [queue.lead?.company.company_id]);

  useEffect(() => {
    if (isAdmin && queue.minExposureScore === 60) {
      queue.loadLead();
    }
  }, [isAdmin]);

  const { company, loading, saving, workflowValues, updateWorkflow } = queue;
  const signals = company ? observedSignals(company) : [];

  return (
    <main className="shell">
      <Topbar title="Your next best prospect" email={session?.user.email ?? null} links={<Link className="nav-link" href="/leads">My leads</Link>} onSignOut={signOut} actions={isAdmin && <button type="button" className="admin-trigger" onClick={() => admin.setAdminModalOpen(true)}>Admin</button>} />

      <QueueBar isAdmin={isAdmin} thresholdDraft={queue.thresholdDraft} minExposureScore={queue.minExposureScore} saving={saving} onThresholdChange={queue.setThresholdDraft} onSaveThreshold={queue.saveThreshold} />

      {isLocalDemo && <div className="demo-banner">Local demo mode: this shows the ranked dataset. Assignment, dispositions, and call activity require an authenticated database session.</div>}
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      {loading ? <section className="panel loading-card"><div className="spinner" /><p>Finding your next account…</p></section> : !company ? <section className="panel empty"><h2>No account loaded</h2><p>Fetch your next best account from the unassigned pool when you are ready.</p><button className="fetch-next" onClick={() => queue.loadLead()} disabled={loading}>{loading ? "Fetching…" : "Get next lead"}</button></section> : (
        <section className="workspace single-lead">
          <aside className="side-stack">
            <AICard aiOutputs={ai.aiOutputs} aiLoading={ai.aiLoading} onRunAi={action => ai.runAi(queue.company?.company_id, action)} />
            <WorkflowCard values={workflowValues} saving={saving} disabled={queue.isLocalDemo} onChange={updateWorkflow} onSaveDisposition={queue.saveDisposition} onSkip={queue.skipLead} />
          </aside>
          <LeadDetail company={company} status={queue.lead?.status ?? ""} signals={signals} />
        </section>
      )}

      <AdminModal open={admin.adminModalOpen} adminUsers={admin.adminUsers} selectedUser={admin.selectedUser} managedUserId={admin.managedUserId} assignmentCompanyId={admin.assignmentCompanyId} adminSaving={admin.adminSaving} authenticated={!!session} onClose={() => admin.setAdminModalOpen(false)} onManagedUserIdChange={admin.setManagedUserId} onAssignmentCompanyIdChange={admin.setAssignmentCompanyId} onUpdateAdminUser={admin.updateAdminUser} onSaveAdminUser={admin.saveAdminUser} onAssignCompany={admin.assignUserCompany} />
    </main>
  );
}