"use client";

import { useState } from "react";
import { AIContentOutput, draftOutreach, summarizeCompany } from "../lib/api";

type AiOutputs = {
  summary: AIContentOutput | null;
  outreach: AIContentOutput | null;
};

type CompletedActions = {
  summary: boolean;
  outreach: boolean;
};

export function useAiAssist(onError: (message: string) => void) {
  const [aiOutputs, setAiOutputs] = useState<AiOutputs>({ summary: null, outreach: null });
  const [aiLoading, setAiLoading] = useState<"summary" | "outreach" | null>(null);
  const [completedActions, setCompletedActions] = useState<CompletedActions>({ summary: false, outreach: false });

  function runAi(companyId: string | undefined, action: "summary" | "outreach") {
    if (!companyId) return;
    setAiLoading(action);
    onError("");
    return (action === "summary" ? summarizeCompany(companyId) : draftOutreach(companyId))
      .then((output) => {
        setAiOutputs(prev => ({ ...prev, [action]: output }));
        setCompletedActions(prev => ({ ...prev, [action]: true }));
      })
      .catch(err => onError(err instanceof Error ? err.message : "AI request failed"))
      .finally(() => setAiLoading(null));
  }

  return {
    aiOutputs,
    aiLoading,
    completedActions,
    runAi,
    resetAi: () => {
      setAiOutputs({ summary: null, outreach: null });
      setCompletedActions({ summary: false, outreach: false });
    }
  };
}