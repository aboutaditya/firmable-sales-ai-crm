"use client";

import { FormEvent, useEffect, useState } from "react";
import { Company, Disposition, QueueLead, getNextLead, getQueuePreferences, listCompanies, updateDisposition, updateQueuePreferences } from "../lib/api";
import { TERMINAL_DISPOSITIONS, dispositionLabels } from "../lib/dispositions";
import { useAuth } from "../components/AuthGate";
import { WorkflowFormValues } from "../components/shared/WorkflowForm";

const DEFAULT_THRESHOLD = 60;

function demoLead(company: Company): QueueLead {
  return { company, status: "demo", disposition: "not_contacted", notes: null, claimed_at: null, next_follow_up_at: null };
}

function tomorrowIso() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString();
}

type QueueLeadDeps = {
  isAdmin: boolean;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

export function useQueueLead({ isAdmin, onError, onNotice }: QueueLeadDeps) {
  const { session } = useAuth();
  const isLocalDemo = !session && process.env.NEXT_PUBLIC_LOCAL_DEMO === "true";
  const [lead, setLead] = useState<QueueLead | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [minExposureScore, setMinExposureScore] = useState(DEFAULT_THRESHOLD);
  const [thresholdDraft, setThresholdDraft] = useState(DEFAULT_THRESHOLD);
  const [disposition, setDisposition] = useState<Disposition>("not_contacted");
  const [notes, setNotes] = useState("");
  const [followUp, setFollowUp] = useState("");

  useEffect(() => {
    setDisposition(lead?.disposition ?? "not_contacted");
    setNotes(lead?.notes ?? "");
    setFollowUp(lead?.next_follow_up_at ? lead.next_follow_up_at.slice(0, 10) : "");
  }, [lead?.company.company_id]);

  async function loadLead(localScore = minExposureScore) {
    setLoading(true);
    onError("");
    onNotice("");
    try {
      if (session) {
        const nextLead = await getNextLead();
        if (isAdmin) {
          const preferences = await getQueuePreferences();
          setMinExposureScore(preferences.min_exposure_score);
          setThresholdDraft(preferences.min_exposure_score);
        }
        setLead(nextLead.lead);
        onNotice(nextLead.message);
      } else {
        const result = await listCompanies({ minScore: String(localScore) });
        setLead(result.items[0] ? demoLead(result.items[0]) : null);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to load your next lead");
    } finally {
      setLoading(false);
    }
  }

  async function saveThreshold(event: FormEvent) {
    event.preventDefault();
    const value = Math.max(0, Math.min(100, thresholdDraft));
    setSaving(true);
    onError("");
    try {
      const preferences = await updateQueuePreferences(value);
      setMinExposureScore(preferences.min_exposure_score);
      setThresholdDraft(preferences.min_exposure_score);
      onNotice("Minimum exposure saved.");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to save queue preference");
    } finally {
      setSaving(false);
    }
  }

  async function saveDisposition(event: FormEvent) {
    event.preventDefault();
    if (!lead || isLocalDemo) return;
    setSaving(true);
    onError("");
    onNotice("");
    try {
      await updateDisposition(lead.company.company_id, {
        disposition,
        notes: notes || undefined,
        next_follow_up_at: followUp ? new Date(`${followUp}T09:00:00`).toISOString() : undefined,
      });
      onNotice(`Saved: ${dispositionLabels[disposition]}`);
      setLead(null);
      await loadLead();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to save disposition");
    } finally {
      setSaving(false);
    }
  }

  async function skipLead() {
    if (!lead || isLocalDemo) return;
    setSaving(true);
    onError("");
    try {
      await updateDisposition(lead.company.company_id, { disposition: "nurture", notes: "Skipped from queue", next_follow_up_at: tomorrowIso() });
      onNotice("Lead skipped. Fetch your next account when ready.");
      setLead(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to move to the next lead");
    } finally {
      setSaving(false);
    }
  }

  const workflowValues: WorkflowFormValues = { disposition, notes, followUp };
  function updateWorkflow(patch: Partial<WorkflowFormValues>) {
    if (patch.disposition !== undefined) setDisposition(patch.disposition);
    if (patch.notes !== undefined) setNotes(patch.notes);
    if (patch.followUp !== undefined) setFollowUp(patch.followUp);
  }

  return {
    lead,
    company: lead?.company ?? null,
    loading,
    saving,
    thresholdDraft,
    minExposureScore,
    isLocalDemo,
    setThresholdDraft,
    workflowValues,
    updateWorkflow,
    loadLead,
    saveThreshold,
    saveDisposition,
    skipLead,
  };
}