"use client";

import { AIContentOutput } from "../../lib/api";

type AiOutputs = {
  summary: AIContentOutput | null;
  outreach: AIContentOutput | null;
};

type AICardProps = {
  aiOutputs: AiOutputs;
  aiLoading: "summary" | "outreach" | null;
  onRunAi: (action: "summary" | "outreach") => void;
};

export default function AICard({ aiOutputs, aiLoading, onRunAi }: AICardProps) {
  const hasAnyOutput = aiOutputs.summary || aiOutputs.outreach;

  return (
    <section className="panel ai-card">
      <div className="section-heading"><div><p className="eyebrow">AI ASSISTANCE</p><h2>Use AI after reviewing evidence</h2></div><span className="ai-badge">Optional</span></div>
      <div className="ai-actions"><button onClick={() => onRunAi("summary")} disabled={!!aiLoading}>{aiLoading === "summary" ? "Writing…" : "Account summary"}</button><button onClick={() => onRunAi("outreach")} disabled={!!aiLoading}>{aiLoading === "outreach" ? "Writing…" : "Draft outreach"}</button></div>
      {hasAnyOutput && (
        <div className="ai-outputs">
          {aiOutputs.summary && (
            <article className="output">
              <div><span className="eyebrow">ACCOUNT SUMMARY</span>{aiOutputs.summary.cached && <span className="cached">Cached</span>}</div>
              <p>{aiOutputs.summary.content}</p>
            </article>
          )}
          {aiOutputs.outreach && (
            <article className="output">
              <div><span className="eyebrow">OUTREACH DRAFT</span>{aiOutputs.outreach.cached && <span className="cached">Cached</span>}</div>
              <p>{aiOutputs.outreach.content}</p>
            </article>
          )}
        </div>
      )}
      <p className="ai-note">AI output is a draft grounded in this account&apos;s observed data. Verify it before sending.</p>
    </section>
  );
}