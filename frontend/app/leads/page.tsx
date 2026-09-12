"use client";

import Link from "next/link";
import { useAuth } from "../../components/AuthGate";
import Topbar from "../../components/shared/Topbar";
import LeadsTable from "../../components/leads/LeadsTable";
import CallWorkflowModal from "../../components/leads/CallWorkflowModal";
import LeadDetailModal from "../../components/leads/LeadDetailModal";
import { useAssignedLeads } from "../../hooks/useAssignedLeads";

const PAGE_SIZE = 10;

export default function AssignedLeadsPage() {
  const { session, signOut } = useAuth();
  const queue = useAssignedLeads();
  const totalPages = Math.max(1, Math.ceil(queue.total / PAGE_SIZE));
  const isLocalDemo = queue.isLocalDemo;

  return (
    <main className="shell">
      <Topbar title="My assigned leads" email={session?.user.email ?? null} links={<Link className="nav-link" href="/">Dashboard</Link>} onSignOut={signOut} />

      {isLocalDemo && <div className="demo-banner">Local demo mode: assigned leads require an authenticated database session.</div>}
      {queue.error && <div className="error">{queue.error}</div>}
      {queue.notice && <div className="notice">{queue.notice}</div>}

      {queue.loading ? <section className="panel loading-card"><div className="spinner" /><p>Loading your leads…</p></section> : (
        <section className="panel">
          {queue.leads.length === 0 ? <div className="empty"><h2>No assigned leads yet</h2><p>Fetch your next account from the dashboard to build out your queue.</p><Link className="button" href="/">Go to dashboard</Link></div> : (
            <LeadsTable leads={queue.leads} page={queue.page} total={queue.total} totalPages={totalPages} hasMore={queue.hasMore} onPrev={() => queue.goTo(queue.page - 1)} onNext={() => queue.goTo(queue.page + 1)} onWorkflow={queue.openWorkflow} onDetail={queue.setDetailLead} />
          )}
        </section>
      )}

      {queue.workflowLead && <CallWorkflowModal lead={queue.workflowLead} values={queue.workflowValues} saving={queue.saving} disabled={queue.isLocalDemo} onValuesChange={queue.updateWorkflow} onSaveDisposition={queue.saveDisposition} onLogCall={queue.logCall} onClose={() => queue.setWorkflowLead(null)} />}
      {queue.detailLead && <LeadDetailModal lead={queue.detailLead} onWorkflow={queue.openWorkflow} onClose={() => queue.setDetailLead(null)} />}
    </main>
  );
}