"use client";

import { ReactNode, useEffect } from "react";

type ModalProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
};

export default function Modal({ eyebrow, title, subtitle, onClose, children }: ModalProps) {
  useEffect(() => {
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="modal modal-full" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2>{subtitle && <p className="muted">{subtitle}</p>}</div>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-inner">{children}</div>
      </div>
    </div>
  );
}