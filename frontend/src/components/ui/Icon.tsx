import type { SVGProps } from "react";

type Name =
  | "home"
  | "team"
  | "memory"
  | "goals"
  | "compass"
  | "chat"
  | "arrow-up"
  | "arrow-right"
  | "plus"
  | "check"
  | "x"
  | "pencil"
  | "trash"
  | "chevron-left"
  | "history";

const PATHS: Record<Name, React.ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5M5 9.5V20h5v-6h4v6h5V9.5" />,
  team: (
    <>
      <circle cx="8.5" cy="9" r="3" />
      <circle cx="17" cy="10" r="2.5" />
      <path d="M3 19c.6-3 3-4.5 5.5-4.5S13.4 16 14 19M15.5 18c.4-2 1.9-3 3.2-3 1.6 0 3 1 3.3 3" />
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
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.8" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" />
    </>
  ),
  chat: <path d="M20 12a7.5 7.5 0 0 1-7.5 7.5H8l-4 2.5.9-3.6A7.5 7.5 0 0 1 12.5 4.5 7.5 7.5 0 0 1 20 12Z" />,
  "arrow-up": <path d="M12 19V5.5M6 11.5l6-6 6 6" />,
  "arrow-right": <path d="M4.5 12h15M13 5.5l6.5 6.5L13 18.5" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m4.5 12.5 5 5L20 6.5" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  pencil: <path d="M4 20h4.5L20 8.5a2.1 2.1 0 0 0-3-3L5.5 17 4 20Z" />,
  trash: <path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 12.5h9L17.5 7" />,
  "chevron-left": <path d="m14.5 5.5-6.5 6.5 6.5 6.5" />,
  history: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.9-6.4L3.5 8" />
      <path d="M3.5 3.5V8h4.5M12 7.5V12l3 2" />
    </>
  ),
};

export function Icon({
  name,
  size = 20,
  strokeWidth = 2.4,
  ...props
}: { name: Name; size?: number; strokeWidth?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      {...props}
    >
      {PATHS[name]}
    </svg>
  );
}
