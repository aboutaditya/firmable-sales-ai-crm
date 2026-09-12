"use client";

import { FormEvent } from "react";
import { QueueLead } from "../../lib/api";
import Modal from "../shared/Modal";
import WorkflowForm, { WorkflowFormValues } from "../shared/WorkflowForm";

type CallWorkflowModalProps = {
  lead: QueueLead;
  values: WorkflowFormValues;
  saving: boolean;
  disabled: boolean;
  onValuesChange: (patch: Partial<WorkflowFormValues>) => void;
  onSaveDisposition: (event: FormEvent) => void;
  onLogCall: (event: FormEvent) => void;
  onClose: () => void;
};

export default function CallWorkflowModal({ lead, values, saving, disabled, onValuesChange, onSaveDisposition, onLogCall, onClose }: CallWorkflowModalProps) {
  return (
    <Modal eyebrow="CALL WORKFLOW" title="Record the human outcome" subtitle={`${lead.company.organization || lead.company.domain} · disposition and call history stay separate from AI assistance.`} onClose={onClose}>
      <WorkflowForm values={values} saving={saving} disabled={disabled} onChange={onValuesChange} onSaveDisposition={onSaveDisposition} onLogCall={onLogCall} />
    </Modal>
  );
}