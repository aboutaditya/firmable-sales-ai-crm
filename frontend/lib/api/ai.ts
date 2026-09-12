import { request } from "./client";
import { AIContentOutput, AssessmentOutput } from "./types";

export function assessCompany(id: string) { return request<AssessmentOutput>(`/companies/${encodeURIComponent(id)}/assess`, { method: "POST" }); }
export function summarizeCompany(id: string) { return request<AIContentOutput>(`/companies/${encodeURIComponent(id)}/summary`, { method: "POST" }); }
export function draftOutreach(id: string) { return request<AIContentOutput>(`/companies/${encodeURIComponent(id)}/outreach`, { method: "POST" }); }