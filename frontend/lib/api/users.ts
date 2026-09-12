import { request } from "./client";
import { AdminUser } from "./types";

export function listAdminUsers() {
  return request<{ items: AdminUser[]; count: number }>("/admin/users");
}