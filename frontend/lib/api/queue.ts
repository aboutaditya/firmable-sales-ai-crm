import { request } from "./client";
import { Disposition, QueueLead, QueueListResponse, QueueNextResponse, QueuePreferences } from "./types";

export function getQueuePreferences() { return request<QueuePreferences>("/me/preferences"); }

export function updateQueuePreferences(minExposureScore: number) {
  return request<QueuePreferences>("/me/preferences", {
    method: "PATCH",
    body: JSON.stringify({ min_exposure_score: minExposureScore }),
  });
}

export function setUserQueuePreferences(userId: string, minExposureScore: number) {
  return request<QueuePreferences>(`/users/${encodeURIComponent(userId)}/queue-preferences`, {
    method: "PATCH",
    body: JSON.stringify({ min_exposure_score: minExposureScore }),
  });
}

export function getNextLead() { return request<QueueNextResponse>("/me/queue/next"); }

export function listAssignedLeads(page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return request<QueueListResponse>(`/me/queue?${params}`);
}

export function updateDisposition(id: string, payload: { disposition: Disposition; notes?: string; next_follow_up_at?: string }) {
  return request<QueueLead>(`/me/queue/${encodeURIComponent(id)}/disposition`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function recordCall(id: string, payload: { outcome: Disposition; notes?: string; next_follow_up_at?: string }) {
  return request<QueueLead>(`/me/queue/${encodeURIComponent(id)}/calls`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}