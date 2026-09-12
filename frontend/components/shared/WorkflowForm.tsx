"use client";

import { FormEvent } from "react";
import { Disposition } from "../../lib/api";
import { CALL_OUTCOMES, dispositionLabels } from "../../lib/dispositions";
import DispositionSelect from "./DispositionSelect";

export type WorkflowFormValues = {
  disposition: Disposition;
  callOutcome: Disposition;
  notes: string;
  followUp: string;
};

export type WorkflowFormProps = {
  values: WorkflowFormValues;
  saving: boolean;
  disabled?: boolean;
  onChange: (patch: Partial<WorkflowFormValues>) => void;
  onSaveDisposition: (event: FormEvent) => void;
  onLogCall: (event: FormEvent) => void;
  onSkip?: () => void;
};

export default function WorkflowForm({ values, saving, disabled = false, onChange, onSaveDisposition, onLogCall, onSkip }: WorkflowFormProps) {
  const blocked = saving || disabled;
  return (
    <>
      <form onSubmit={onSaveDisposition} className="workflow-form">
        <DispositionSelect value={values.disposition} onChange={disposition => onChange({ disposition })} options={Object.keys(dispositionLabels) as Disposition[]} />
        <label>Follow-up date<input type="date" value={values.followUp} onChange={event => onChange({ followUp: event.target.value })} /></label>
        <label>Notes<textarea value={values.notes} onChange={event => onChange({ notes: event.target.value })} placeholder="What did you learn?" rows={4} /></label>
        <div className="form-actions"><button disabled={blocked}>{saving ? "Saving…" : "Save disposition"}</button>{onSkip && <button type="button" className="secondary" onClick={onSkip} disabled={blocked}>Skip lead</button>}</div>
      </form>
      <form onSubmit={onLogCall} className="call-form">
        <DispositionSelect value={values.callOutcome} onChange={callOutcome => onChange({ callOutcome })} options={CALL_OUTCOMES} label="Call outcome" />
        <button className="secondary" disabled={blocked}>{saving ? "Saving…" : "Log call activity"}</button>
      </form>
    </>
  );
}