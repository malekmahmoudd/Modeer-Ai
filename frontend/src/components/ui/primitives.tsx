"use client";

import { InkRule } from "@/components/art/Ink";

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-[18px] w-[18px] animate-spin rounded-full border-[3px] border-ink border-t-transparent ${className}`}
    />
  );
}

export function ThinkingDots({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`} role="status" aria-label="Thinking">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="dot-pulse h-2 w-2 rounded-full bg-pink"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  );
}

/** Big page title: heavy display type over an eyebrow, with an ink rule under. */
export function PageHeader({
  eyebrow,
  title,
  lede,
  action,
}: {
  eyebrow?: string;
  title: string;
  lede?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="mb-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
          <h1 className="display text-[clamp(30px,5vw,46px)] text-ink">{title}</h1>
          {lede && (
            <p className="mt-3 max-w-[52ch] text-[15px] leading-relaxed text-ink-soft">{lede}</p>
          )}
        </div>
        {action}
      </div>
      <InkRule className="mt-5" />
    </header>
  );
}

/** Section heading with a rule running to the right, optional aside at the end. */
export function SectionHead({
  title,
  aside,
  className = "",
}: {
  title: string;
  aside?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mb-5 flex items-center gap-4 ${className}`}>
      <h2 className="display shrink-0 text-[clamp(24px,3.4vw,34px)] text-ink">{title}</h2>
      <span className="h-[2px] flex-1 bg-ink" aria-hidden />
      {aside}
    </div>
  );
}

export function SectionLabel({
  children,
  action,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="eyebrow">{children}</h2>
      {action}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="border-2 border-dashed border-ink bg-paper-hi px-6 py-10 text-center">
      <p className="display text-[19px] text-ink">{title}</p>
      {children && (
        <p className="mx-auto mt-2 max-w-[46ch] text-[14px] leading-relaxed text-ink-soft">
          {children}
        </p>
      )}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="border-2 border-ink bg-pink-pale px-3.5 py-2.5 text-[13.5px] font-semibold text-ink"
    >
      {message}
    </p>
  );
}
