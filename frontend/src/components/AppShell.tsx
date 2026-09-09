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
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: user } = useApi<UserProfile>("/users/me");
  const name = firstName(user?.display_name);

  // The agent workspace manages its own full-height layout.
  const inWorkspace = pathname.startsWith("/agents/");

  return (
    <div className="flex min-h-screen w-full">
      {/* Desktop rail */}
      <aside
        className="fixed inset-y-0 left-0 z-30 hidden flex-col justify-between border-r border-line px-4 py-6 lg:flex"
        style={{ width: "var(--nav-w)" }}
      >
        <div>
          <div className="px-1.5">
            <Brand />
          </div>
          <nav className="mt-8 flex flex-col gap-0.5">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13.5px] transition ${
                    active
                      ? "bg-surface-strong font-medium text-white"
                      : "text-content-dim hover:bg-surface hover:text-white"
                  }`}
                >
                  <Icon name={item.icon} size={17} className={active ? "text-accent" : ""} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-content-dim">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-surface-strong text-[12px] font-semibold text-white">
            {(name || "Y").charAt(0).toUpperCase()}
          </span>
          <span className="text-[12.5px]">{name || "Your space"}</span>
        </div>
      </aside>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-[var(--nav-w)]">
        {/* Mobile top bar — hidden in the agent workspace (it has its own header) */}
        {!inWorkspace && (
          <header className="sticky top-0 z-20 flex items-center border-b border-line bg-bg/85 px-4 py-3 backdrop-blur-md lg:hidden">
            <Brand />
          </header>
        )}

        <main
          className={
            inWorkspace
              ? "min-w-0 flex-1"
              : "mx-auto min-w-0 flex-1 px-5 py-7 pb-28 sm:px-9 sm:py-11 lg:pb-16 w-full max-w-[1140px]"
          }
        >
          {children}
        </main>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-lg lg:hidden">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-1 py-2.5 text-[10.5px] ${
                active ? "text-white" : "text-content-faint"
              }`}
            >
              <Icon name={item.icon} size={20} className={active ? "text-accent" : ""} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
