import { request } from "./client";
import { Company } from "./types";

export function listCompanies(filters: { country?: string; minScore?: string; industry?: string; minEmployees?: string; signals?: string[]; cursor?: string }) {
  const params = new URLSearchParams({ limit: "100" });
  if (filters.country) params.set("country", filters.country);
  if (filters.minScore) params.set("min_score", filters.minScore);
  if (filters.industry) params.set("industry", filters.industry);
  if (filters.minEmployees) params.set("min_employee_count", filters.minEmployees);
  for (const signal of filters.signals ?? []) params.append("signal", signal);
  if (filters.cursor) params.set("cursor", filters.cursor);
  return request<{ items: Company[]; count: number; next_cursor?: string | null }>(`/companies?${params}`);
}

export function getCompany(id: string) { return request<Company>(`/companies/${encodeURIComponent(id)}`); }

export function assignCompany(companyId: string, userId: string) {
  return request<{ status: string; company_id: string; user_id: string }>(`/companies/${encodeURIComponent(companyId)}/assign`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}