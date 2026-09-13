"use client";

import { FormEvent, useEffect, useState } from "react";
import { QueueLead, listAssignedLeads, updateDisposition } from "../lib/api";
import { dispositionLabels } from "../lib/dispositions";
import { useAuth } from "../components/AuthGate";
import { WorkflowFormValues } from "../components/shared/WorkflowForm";

const PAGE_SIZE = 10;

export function useAssignedLeads() {
  const { session } = useAuth();
  const isLocalDemo = !session && process.env.NEXT_PUBLIC_LOCAL_DEMO === "true";
  const [leads, setLeads] = useState<QueueLead[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detailLead, setDetailLead] = useState<QueueLead | null>(null);
  const [workflowLead, setWorkflowLead] = useState<QueueLead | null>(null);
  const [workflowValues, setWorkflowValues] = useState<WorkflowFormValues>({ disposition: "not_contacted", notes: "", followUp: "" });

  function load(targetPage = page) {
    setError("");
    return listAssignedLeads(targetPage, PAGE_SIZE).then(result => {
      setLeads(result.items);
      setTotal(result.count);
      setHasMore(result.has_more);
      setPage(result.page);
    }).catch(err => { setError(err instanceof Error ? err.message : "Unable to load your leads"); });
  }

  function goTo(targetPage: number) {
    setLoading(true);
    load(targetPage).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!session) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    load(1).then(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  function openWorkflow(lead: QueueLead) {
    setDetailLead(null);
    setWorkflowLead(lead);
    setWorkflowValues({ disposition: lead.disposition ?? "not_contacted", notes: lead.notes ?? "", followUp: lead.next_follow_up_at ? lead.next_follow_up_at.slice(0, 10) : "" });
    setError("");
  }

  function updateWorkflow(patch: Partial<WorkflowFormValues>) {
    setWorkflowValues(values => ({
      disposition: patch.disposition ?? values.disposition,
      notes: patch.notes ?? values.notes,
      followUp: patch.followUp ?? values.followUp,
    }));
  }

  async function saveDisposition(event: FormEvent) {
    event.preventDefault();
    if (!workflowLead || isLocalDemo || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await updateDisposition(workflowLead.company.company_id, {
        disposition: workflowValues.disposition,
        notes: workflowValues.notes || undefined,
        next_follow_up_at: workflowValues.followUp ? new Date(`${workflowValues.followUp}T09:00:00`).toISOString() : undefined,
      });
      setNotice(`Saved: ${dispositionLabels[workflowValues.disposition]}`);
      setWorkflowLead(null);
      goTo(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save disposition");
    } finally {
      setSaving(false);
    }
  }

  return {
    leads,
    page,
    total,
    hasMore,
    loading,
    saving,
    error,
    notice,
    setError,
    setNotice,
    isLocalDemo,
    detailLead,
    setDetailLead,
    workflowLead,
    setWorkflowLead,
    workflowValues,
    updateWorkflow,
    openWorkflow,
    goTo,
    saveDisposition,
  };
}