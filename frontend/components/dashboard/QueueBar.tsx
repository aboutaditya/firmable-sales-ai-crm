"use client";

import { FormEvent } from "react";

type QueueBarProps = {
  isAdmin: boolean;
  thresholdDraft: number;
  minExposureScore: number;
  saving: boolean;
  onThresholdChange: (value: number) => void;
  onSaveThreshold: (event: FormEvent) => void;
};

export default function QueueBar({ isAdmin, thresholdDraft, minExposureScore, saving, onThresholdChange, onSaveThreshold }: QueueBarProps) {
  return (
    <section className="queue-bar">
      <div><p className="eyebrow">PERSONAL QUEUE</p><h2>One account in focus at a time</h2><p className="muted">Your next prospect is the highest-scoring account that no one is assigned to yet.</p></div>
      {isAdmin && <form className="threshold" onSubmit={onSaveThreshold}>
        <label htmlFor="threshold">Minimum exposure</label>
        <div className="threshold-controls"><input id="threshold" type="range" min="0" max="100" value={thresholdDraft} onChange={event => onThresholdChange(Number(event.target.value))} /><output>{thresholdDraft}</output><button disabled={saving || thresholdDraft === minExposureScore}>{saving ? "Saving…" : "Save"}</button></div>
      </form>}
    </section>
  );
}