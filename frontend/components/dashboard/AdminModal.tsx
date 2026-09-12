"use client";

import { FormEvent } from "react";
import { AdminUser } from "../../lib/api";
import Modal from "../shared/Modal";

type AdminModalProps = {
  open: boolean;
  adminUsers: AdminUser[];
  selectedUser?: AdminUser;
  managedUserId: string;
  assignmentCompanyId: string;
  adminSaving: boolean;
  authenticated: boolean;
  onClose: () => void;
  onManagedUserIdChange: (userId: string) => void;
  onAssignmentCompanyIdChange: (value: string) => void;
  onUpdateAdminUser: (user: AdminUser) => void;
  onSaveAdminUser: (user: AdminUser) => void;
  onAssignCompany: (event: FormEvent) => void;
};

export default function AdminModal({
  open,
  adminUsers,
  selectedUser,
  managedUserId,
  assignmentCompanyId,
  adminSaving,
  authenticated,
  onClose,
  onManagedUserIdChange,
  onAssignmentCompanyIdChange,
  onUpdateAdminUser,
  onSaveAdminUser,
  onAssignCompany,
}: AdminModalProps) {
  if (!open) return null;
  return (
    <Modal eyebrow="ADMIN CONSOLE" title="Set thresholds & assign accounts" subtitle="Manage sales reps while you work." onClose={onClose}>
      {adminUsers.length === 0 ? <p className="muted">No users found. Configure the Supabase service-role key or create an assignment first.</p> : <label className="admin-field">User<select value={managedUserId} onChange={event => onManagedUserIdChange(event.target.value)}>{adminUsers.map(item => <option key={item.user_id} value={item.user_id}>{item.email || item.display_name || item.user_id} · {item.assigned_count} assigned</option>)}</select></label>}
      {selectedUser && <div className="admin-user-detail">
        <label className="admin-field">Min exposure<input type="number" min="0" max="100" value={selectedUser.min_exposure_score} onChange={event => onUpdateAdminUser({ ...selectedUser, min_exposure_score: Number(event.target.value) })} /></label>
        <button onClick={() => onSaveAdminUser(selectedUser)} disabled={adminSaving || !authenticated}>{adminSaving ? "Saving…" : "Save threshold"}</button>
        <form onSubmit={onAssignCompany} className="admin-assign"><label className="admin-field">Company ID / domain<input value={assignmentCompanyId} onChange={event => onAssignmentCompanyIdChange(event.target.value)} placeholder="company.example" required /></label><button type="submit" disabled={adminSaving || !managedUserId}>{adminSaving ? "Saving…" : "Assign company"}</button></form>
      </div>}
    </Modal>
  );
}