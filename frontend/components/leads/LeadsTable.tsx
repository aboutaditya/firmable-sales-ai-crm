"use client";

import { QueueLead } from "../../lib/api";
import LeadRow from "./LeadRow";

type LeadsTableProps = {
  leads: QueueLead[];
  page: number;
  total: number;
  totalPages: number;
  hasMore: boolean;
  onPrev: () => void;
  onNext: () => void;
  onWorkflow: (lead: QueueLead) => void;
  onDetail: (lead: QueueLead) => void;
};

export default function LeadsTable({ leads, page, total, totalPages, hasMore, onPrev, onNext, onWorkflow, onDetail }: LeadsTableProps) {
  return (
    <div className="lead-grid-wrap">
      <div className="lead-head"><span>Account</span><span>Score</span><span>Status</span><span>Disposition</span><span>Follow-up</span><span>Notes</span><span>Actions</span></div>
      {leads.map(lead => <LeadRow key={lead.company.company_id} lead={lead} onWorkflow={onWorkflow} onDetail={onDetail} />)}
      <div className="page-controls">
        <span className="page-meta">{total} assigned · page {page} of {totalPages}</span>
        <div className="page-nav"><button type="button" className="text" onClick={onPrev} disabled={page <= 1}>← Prev</button><button type="button" className="text" onClick={onNext} disabled={!hasMore}>Next →</button></div>
      </div>
    </div>
  );
}