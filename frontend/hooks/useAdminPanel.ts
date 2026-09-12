"use client";

import { FormEvent, useEffect, useState } from "react";
import { AdminUser, assignCompany, listAdminUsers, setUserQueuePreferences } from "../lib/api";

type AdminPanelDeps = {
  isAdmin: boolean;
  authenticated: boolean;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

export function useAdminPanel({ isAdmin, authenticated, onError, onNotice }: AdminPanelDeps) {
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [managedUserId, setManagedUserId] = useState("");
  const [assignmentCompanyId, setAssignmentCompanyId] = useState("");
  const [adminSaving, setAdminSaving] = useState(false);
  const [adminModalOpen, setAdminModalOpen] = useState(false);

  useEffect(() => {
    if (!isAdmin) {
      setAdminUsers([]);
      return;
    }
    listAdminUsers()
      .then(result => setAdminUsers(result.items))
      .catch(err => onError(err instanceof Error ? err.message : "Unable to load users"));
  }, [isAdmin, onError]);

  const selectedUser = adminUsers.find(item => item.user_id === managedUserId);

  function updateAdminUser(user: AdminUser) {
    setAdminUsers(users => users.map(item => item.user_id === user.user_id ? user : item));
  }

  async function saveAdminUser(userToUpdate: AdminUser) {
    if (!authenticated) return;
    setAdminSaving(true);
    onError("");
    try {
      const updated = await setUserQueuePreferences(userToUpdate.user_id, userToUpdate.min_exposure_score);
      setAdminUsers(users => users.map(item => item.user_id === userToUpdate.user_id ? { ...item, min_exposure_score: updated.min_exposure_score } : item));
      onNotice(`Threshold saved for ${userToUpdate.email || userToUpdate.user_id}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to save user preference");
    } finally {
      setAdminSaving(false);
    }
  }

  async function assignUserCompany(event: FormEvent) {
    event.preventDefault();
    if (!managedUserId || !assignmentCompanyId) return;
    setAdminSaving(true);
    onError("");
    try {
      await assignCompany(assignmentCompanyId, managedUserId);
      onNotice(`${assignmentCompanyId} assigned to ${managedUserId}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Unable to assign company");
    } finally {
      setAdminSaving(false);
    }
  }

  return {
    adminUsers,
    managedUserId,
    setManagedUserId,
    assignmentCompanyId,
    setAssignmentCompanyId,
    adminSaving,
    adminModalOpen,
    setAdminModalOpen,
    selectedUser,
    updateAdminUser,
    saveAdminUser,
    assignUserCompany,
  };
}