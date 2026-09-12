"use client";

import { useState } from "react";
import { AIContentOutput, draftOutreach, summarizeCompany } from "../lib/api";

export function useAiAssist(onError: (message: string) => void) {
  const [aiOutput, setAiOutput] = useState<AIContentOutput | null>(null);
  const [aiLoading, setAiLoading] = useState<"summary" | "outreach" | null>(null);

  function runAi(companyId: string | undefined, action: "summary" | "outreach") {
    if (!companyId) return;
    setAiLoading(action);
    onError("");
    return (action === "summary" ? summarizeCompany(companyId) : draftOutreach(companyId))
      .then(setAiOutput)
      .catch(err => onError(err instanceof Error ? err.message : "AI request failed"))
      .finally(() => setAiLoading(null));
  }

  return { aiOutput, aiLoading, runAi, resetAi: () => setAiOutput(null) };
}