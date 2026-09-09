"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Brand } from "@/components/Brand";
import { Icon } from "@/components/ui/Icon";
import { useApi } from "@/lib/api";
import { firstName } from "@/lib/format";
import type { UserProfile } from "@/types";

const NAV = [
  { href: "/", label: "Home", icon: "home" as const },
  { href: "/team", label: "Team", icon: "team" as const },
  { href: "/memory", label: "Memory", icon: "memory" as const },
  { href: "/goals", label: "Goals", icon: "goals" as const },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/team") return pathname.startsWith("/team") || pathname.startsWith("/agents");
  return pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: user } = useApi<UserProfile>("/users/me");
  const name = firstName(user?.display_name);

  // The agent workspace owns its own full-height layout.
  const inWorkspace = pathname.startsWith("/agents/");

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      {/* ---------- top navigation ---------- */}
      <header className="sticky top-0 z-40 border-b-2 border-ink bg-paper">
        <div className="mx-auto flex h-[var(--nav-h)] w-full max-w-page items-center gap-6 px-4 sm:px-7">
          <Brand size="sm" />

          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className="relative px-3 py-2 text-[15px] font-bold text-ink transition hover:text-pink-deep"
                >
                  {item.label}
                  <span
                    className={`absolute inset-x-2 -bottom-0.5 h-[4px] rounded-full bg-pink transition-opacity ${
                      active ? "opacity-100" : "opacity-0"
                    }`}
                    aria-hidden
                  />
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {name && (
              <span className="hidden items-center gap-2 sm:flex">
                <span className="text-[13px] font-semibold text-ink-soft">{name}</span>
                <span
                  className="grid h-9 w-9 place-items-center rounded-full border-2 border-ink bg-sun text-[13px] font-black"
                  aria-hidden
                >
                  {name.charAt(0).toUpperCase()}
                </span>
              </span>
            )}
          </div>
        </div>
      </header>

      {/* ---------- page ---------- */}
      <main
        id="main"
        className={
          inWorkspace
            ? "flex min-h-0 flex-1 flex-col"
            : "mx-auto w-full max-w-page flex-1 px-4 pb-28 pt-7 sm:px-7 sm:pt-10 md:pb-16"
        }
      >
        {children}
      </main>

      {/* ---------- mobile tab bar ---------- */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t-2 border-ink bg-paper pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Main"
      >
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className="relative flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-bold text-ink"
            >
              {active && (
                <span className="absolute inset-x-5 top-0 h-[4px] bg-pink" aria-hidden />
              )}
              <Icon name={item.icon} size={20} className={active ? "text-pink-deep" : "text-ink-soft"} />
              <span className={active ? "text-ink" : "text-ink-soft"}>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
