"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useDesignText } from "./text";
export function Drawer({
  title,
  children,
  onClose
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const t = useDesignText();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return <dialog ref={ref} aria-label={title} className="design-drawer" onCancel={e => {
    e.preventDefault();
    onClose();
  }} onClick={e => {
    if (e.target === e.currentTarget) onClose();
  }}>
    <div className="min-h-full bg-paper-hi p-5 sm:p-7">
      <header className="mb-5 flex items-center justify-between gap-3"><h2 className="display text-2xl">{title}</h2><button autoFocus className="btn" onClick={onClose}>{t("close")}</button></header>
      {children}
    </div>
  </dialog>;
}
