"use client";

import { QueueLead } from "../../lib/api";
import { dispositionLabels } from "../../lib/dispositions";

type LeadRowProps = {
  lead: QueueLead;
  onWorkflow: (lead: QueueLead) => void;
  onDetail: (lead: QueueLead) => void;
};

export default function LeadRow({ lead, onWorkflow, onDetail }: LeadRowProps) {
  const company = lead.company;
  return (
    <div className="lead-row">
      <div className="lead-identity"><h3>{company.organization || company.domain}</h3><small>{company.domain}{company.country ? ` · ${company.country}` : ""}</small></div>
      <span className="lead-score">{company.security_score}<small>/100</small></span>
      <span className="queue-status">{lead.status.replace("_", " ")}</span>
      <span className="lead-disposition">{lead.disposition ? dispositionLabels[lead.disposition] : "—"}</span>
      <span className="lead-followup">{lead.next_follow_up_at ? lead.next_follow_up_at.slice(0, 10) : "—"}</span>
      <p className="lead-notes">{lead.notes || "—"}</p>
      <div className="lead-actions"><button onClick={() => onWorkflow(lead)}>Call disposition</button><button className="secondary" onClick={() => onDetail(lead)}>Details</button></div>
    </div>
  );
}