"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Home", icon: "◎" },
  { href: "/team", label: "AI Team", icon: "❖" },
  { href: "/memory", label: "Memory", icon: "❒" },
  { href: "/goals", label: "Goals", icon: "✦" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1400px]">
      <aside className="sticky top-0 hidden h-screen w-[240px] shrink-0 flex-col gap-1 border-r border-white/[0.06] px-4 py-6 md:flex">
        <Link href="/" className="mb-6 flex items-center gap-2.5 px-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 text-lg shadow-lg shadow-violet-900/40">
            🧭
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-tight text-white">Modeer</span>
            <span className="block text-[11px] text-white/40">Personal AI Team</span>
          </span>
        </Link>

        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                  active
                    ? "bg-white/[0.08] text-white"
                    : "text-white/55 hover:bg-white/[0.04] hover:text-white/90"
                }`}
              >
                <span className="text-white/40">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[11px] leading-relaxed text-white/40">
          Modeer keeps the context your whole team shares. Talk to any specialist
          directly — you never have to go through Modeer.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-white/[0.06] bg-ink-950/70 px-4 py-3 backdrop-blur-xl md:hidden">
          <span className="text-base">🧭</span>
          <span className="text-sm font-semibold">Modeer</span>
          <nav className="ml-auto flex gap-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-lg px-2.5 py-1.5 text-xs text-white/60 hover:bg-white/10"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-10">{children}</main>
      </div>
    </div>
  );
}
