"use client";

import { QueueLead } from "../../lib/api";
import { dispositionLabels, observedSignals } from "../../lib/dispositions";
import Modal from "../shared/Modal";

type LeadDetailModalProps = {
  lead: QueueLead;
  onWorkflow: (lead: QueueLead) => void;
  onClose: () => void;
};

export default function LeadDetailModal({ lead, onWorkflow, onClose }: LeadDetailModalProps) {
  const signals = observedSignals(lead.company);
  return (
    <Modal eyebrow="LEAD DETAIL" title={lead.company.organization || lead.company.domain} subtitle={`${lead.company.domain} · ${lead.company.city || ""}${lead.company.country ? ` · ${lead.company.country}` : ""}`} onClose={onClose}>
      <div className="lead-meta"><span className="queue-status">{lead.status.replace("_", " ")}</span>{lead.disposition && <span className="queue-status">{dispositionLabels[lead.disposition]}</span>}{lead.next_follow_up_at && <span className="queue-status">Follow-up {lead.next_follow_up_at.slice(0, 10)}</span>}</div>
      <div className="score-card"><span>Observed exposure score</span><strong>{lead.company.security_score}<small>/100</small></strong></div>
      <p className="score-note">A prioritisation signal from observed external security data. It is not proof of a breach or buying intent.</p>
      <div className="metrics"><div><b>{lead.company.asset_count}</b><span>Assets</span></div><div><b>{lead.company.vulnerability_count}</b><span>Vulnerabilities</span></div><div><b>{lead.company.critical_vulnerability_count}</b><span>Critical</span></div><div><b>{lead.company.eol_product_count}</b><span>EOL products</span></div></div>
      <section className="evidence"><p className="eyebrow">WHY THIS ACCOUNT</p><ul>{signals.length ? signals.map(signal => <li key={signal}>{signal}</li>) : <li>No strong exposure signal observed</li>}</ul></section>
      <section className="evidence"><p className="eyebrow">NOTES</p><p className="muted">{lead.notes || "No notes recorded."}</p></section>
      <div className="form-actions"><button onClick={() => onWorkflow(lead)}>Call disposition</button><button className="secondary" onClick={onClose}>Close</button></div>
    </Modal>
  );
}