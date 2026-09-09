"use client";

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/15 border-t-white/70 ${className}`}
    />
  );
}

export function ThinkingDots({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="thinking-dot h-1.5 w-1.5 rounded-full bg-content-faint"
          style={{ animationDelay: `${i * 0.16}s` }}
        />
      ))}
    </span>
  );
}

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
    <div className="mb-7 flex items-end justify-between gap-6">
      <div>
        {eyebrow && (
          <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-content-faint">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[25px] font-semibold leading-tight tracking-[-0.02em] text-white">
          {title}
        </h1>
        {lede && <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-content-dim">{lede}</p>}
      </div>
      {action}
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
    <div className="mb-4 flex items-center justify-between">
      <h2 className="text-[13px] font-semibold uppercase tracking-[0.12em] text-content-faint">
        {children}
      </h2>
      {action}
    </div>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-12 text-center">
      <p className="text-[14px] font-medium text-white">{title}</p>
      {children && <p className="max-w-sm text-[13.5px] leading-relaxed text-content-dim">{children}</p>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-[10px] border border-red-500/25 bg-red-500/[0.08] px-3.5 py-2.5 text-[13px] text-red-200">
      {message}
    </div>
  );
}
