"use client";

import { AIContentOutput } from "../../lib/api";

type AICardProps = {
  aiOutput: AIContentOutput | null;
  aiLoading: "summary" | "outreach" | null;
  onRunAi: (action: "summary" | "outreach") => void;
};

export default function AICard({ aiOutput, aiLoading, onRunAi }: AICardProps) {
  return (
    <section className="panel ai-card">
      <div className="section-heading"><div><p className="eyebrow">AI ASSISTANCE</p><h2>Use AI after reviewing evidence</h2></div><span className="ai-badge">Optional</span></div>
      <div className="ai-actions"><button onClick={() => onRunAi("summary")} disabled={!!aiLoading}>{aiLoading === "summary" ? "Writing…" : "Account summary"}</button><button onClick={() => onRunAi("outreach")} disabled={!!aiLoading}>{aiLoading === "outreach" ? "Writing…" : "Draft outreach"}</button></div>
      {aiOutput && <article className="output"><div><span className="eyebrow">{aiOutput.feature === "company_summary" ? "ACCOUNT SUMMARY" : "OUTREACH DRAFT"}</span>{aiOutput.cached && <span className="cached">Cached</span>}</div><p>{aiOutput.content}</p></article>}
      <p className="ai-note">AI output is a draft grounded in this account&apos;s observed data. Verify it before sending.</p>
    </section>
  );
}