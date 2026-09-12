"use client";

import WorkflowForm, { WorkflowFormProps } from "../shared/WorkflowForm";

export default function WorkflowCard(props: WorkflowFormProps) {
  return (
    <section className="panel workflow-card">
      <p className="eyebrow">CALL WORKFLOW</p><h2>Record the human outcome</h2><p className="muted">Keep disposition and call history separate from AI assistance.</p>
      <WorkflowForm {...props} />
    </section>
  );
}