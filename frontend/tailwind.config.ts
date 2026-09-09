import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        brush: ["var(--font-brush)", "cursive"],
        hand: ["var(--font-hand)", "cursive"],
      },
      colors: {
        paper: {
          DEFAULT: "var(--paper)",
          hi: "var(--paper-hi)",
          lo: "var(--paper-lo)",
        },
        sun: {
          DEFAULT: "var(--sun)",
          deep: "var(--sun-deep)",
          pale: "var(--sun-pale)",
        },
        pink: {
          DEFAULT: "var(--pink)",
          deep: "var(--pink-deep)",
          pale: "var(--pink-pale)",
        },
        ink: {
          DEFAULT: "var(--ink)",
          soft: "var(--ink-soft)",
          faint: "var(--ink-faint)",
        },
        navy: "var(--navy)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        pop: "var(--pop)",
        "pop-sm": "var(--pop-sm)",
        "pop-xs": "var(--pop-xs)",
      },
      maxWidth: {
        page: "1240px",
        read: "46rem",
      },
    },
  },
  plugins: [],
};

export default config;
