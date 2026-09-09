"use client";

import { useEffect, useRef } from "react";

import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/primitives";

export function Composer({
  value,
  onChange,
  onSend,
  disabled,
  streaming,
  placeholder,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  streaming?: boolean;
  placeholder: string;
  autoFocus?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const canSend = value.trim().length > 0 && !streaming && !disabled;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSend();
      }}
      className="flex items-end gap-2 rounded-[14px] border border-line bg-bg-elev p-2 pl-3.5 transition focus-within:border-line-strong"
    >
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (canSend) onSend();
          }
        }}
        placeholder={placeholder}
        className="max-h-[200px] min-h-[26px] flex-1 resize-none bg-transparent py-1.5 text-[14px] leading-relaxed text-white outline-none placeholder:text-content-faint"
      />
      <button
        type="submit"
        disabled={!canSend}
        aria-label="Send"
        className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px] transition disabled:opacity-35"
        style={{
          background: canSend ? "var(--accent)" : "var(--surface-strong)",
          color: canSend ? "var(--accent-contrast)" : "var(--text-faint)",
        }}
      >
        {streaming ? <Spinner className="h-4 w-4" /> : <Icon name="arrow-up" size={17} />}
      </button>
    </form>
  );
}
