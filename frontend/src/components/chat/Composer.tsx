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
    el.style.height = `${Math.min(el.scrollHeight, 190)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus && window.matchMedia("(min-width: 768px)").matches) ref.current?.focus();
  }, [autoFocus]);

  const canSend = value.trim().length > 0 && !streaming && !disabled;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSend();
      }}
      className="flex items-end gap-2 rounded-lg border-2 border-ink bg-paper-hi p-2 pl-3.5 shadow-pop-xs transition focus-within:border-pink focus-within:shadow-pop-sm"
    >
      <label htmlFor="composer" className="sr-only">
        {placeholder}
      </label>
      <textarea
        id="composer"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSend();
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
        className="max-h-[190px] min-h-[28px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-faint focus-visible:outline-none"
      />
      <button
        type="submit"
        disabled={!canSend}
        aria-label={streaming ? "Sending" : "Send message"}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-ink transition disabled:opacity-40"
        style={{
          background: canSend ? "var(--pink)" : "var(--paper-lo)",
          color: canSend ? "var(--ink)" : "var(--ink-faint)",
        }}
      >
        {streaming ? <Spinner className="!h-4 !w-4 !border-white !border-t-transparent" /> : <Icon name="arrow-up" size={20} strokeWidth={2.8} />}
      </button>
    </form>
  );
}
