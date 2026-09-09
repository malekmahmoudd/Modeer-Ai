import type { SVGProps } from "react";

type Name =
  | "home"
  | "team"
  | "memory"
  | "goals"
  | "compass"
  | "arrow-up"
  | "arrow-right"
  | "plus"
  | "check"
  | "x"
  | "sparkle"
  | "pencil"
  | "trash"
  | "chevron-left"
  | "history";

const PATHS: Record<Name, React.ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5M5 9.5V20h5v-6h4v6h5V9.5" />,
  team: (
    <>
      <circle cx="8" cy="9" r="3" />
      <circle cx="17" cy="10" r="2.5" />
      <path d="M2.5 19c.6-3 3-4.5 5.5-4.5S12.9 16 13.5 19M15 18c.4-2 1.9-3 3.2-3 1.6 0 3 1 3.3 3" />
    </>
  ),
  memory: (
    <>
      <path d="M9 4.5a3 3 0 0 0-3 3 3 3 0 0 0-1.5 5.4A3 3 0 0 0 6 18.5a3 3 0 0 0 5.9.8V5.4A3 3 0 0 0 9 4.5Z" />
      <path d="M15 4.5a3 3 0 0 1 3 3 3 3 0 0 1 1.5 5.4A3 3 0 0 1 18 18.5a3 3 0 0 1-5.9.8" />
    </>
  ),
  goals: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" />
    </>
  ),
  "arrow-up": <path d="M12 19V5M6 11l6-6 6 6" />,
  "arrow-right": <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m4 12 5 5L20 6" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  sparkle: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />,
  pencil: <path d="M4 20h4L19 9a2 2 0 0 0-3-3L5 17v3Z" />,
  trash: <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />,
  "chevron-left": <path d="m14 6-6 6 6 6" />,
  history: (
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 4v4h4M12 8v4l3 2" />
    </>
  ),
};

export function Icon({
  name,
  size = 18,
  ...props
}: { name: Name; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {PATHS[name]}
    </svg>
  );
}
