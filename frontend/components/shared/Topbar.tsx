"use client";

import { ReactNode } from "react";

type TopbarProps = {
  title: string;
  eyebrow?: string;
  email?: string | null;
  links?: ReactNode;
  actions?: ReactNode;
  onSignOut: () => Promise<void>;
};

export default function Topbar({ title, eyebrow = "SALES INTELLIGENCE", email, links, actions, onSignOut }: TopbarProps) {
  return (
    <header className="topbar">
      <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>
      <div className="account">{links}{actions}<span>{email ?? "Local demo"}</span>{email && <button onClick={onSignOut}>Sign out</button>}</div>
    </header>
  );
}