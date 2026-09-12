"use client";

import { Company } from "../../lib/api";

type LeadDetailProps = {
  company: Company;
  status: string;
  signals: string[];
};

export default function LeadDetail({ company, status, signals }: LeadDetailProps) {
  return (
    <article className="panel detail">
      <div className="lead-header"><div><p className="eyebrow">CURRENT ACCOUNT</p><h2>{company.organization || company.domain}</h2><p className="muted">{company.domain} · {company.city || ""} {company.country || ""}</p></div><span className="queue-status">{status.replace("_", " ")}</span></div>
      <div className="score-card"><span>Observed exposure score</span><strong>{company.security_score}<small>/100</small></strong></div>
      <p className="score-note">A prioritisation signal from observed external security data. It is not proof of a breach or buying intent.</p>
      <div className="metrics"><div><b>{company.asset_count}</b><span>Assets</span></div><div><b>{company.vulnerability_count}</b><span>Vulnerabilities</span></div><div><b>{company.critical_vulnerability_count}</b><span>Critical</span></div><div><b>{company.eol_product_count}</b><span>EOL products</span></div></div>
      <section className="evidence"><p className="eyebrow">WHY THIS ACCOUNT</p><ul>{signals.length ? signals.map(signal => <li key={signal}>{signal}</li>) : <li>No strong exposure signal observed</li>}</ul></section>
    </article>
  );
}