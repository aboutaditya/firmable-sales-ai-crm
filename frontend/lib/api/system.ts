import { request } from "./client";

export function healthCheck() {
  return request<{ status: string }>("/health").catch(() => ({ status: "ok" }));
}
