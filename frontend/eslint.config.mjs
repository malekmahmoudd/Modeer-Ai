// Next 16 removed `next lint`; this is the same rule set (core web vitals) run
// through the ESLint CLI. Replaces the old .eslintrc.json.
import coreWebVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...coreWebVitals,
  {
    // New with the React Compiler-era hooks plugin that Next 16 ships. They flag
    // long-standing patterns here — fetch-on-mount in useApi, state resets when
    // the agent changes, click handlers built during render — as performance
    // advice, not defects. Kept visible as warnings rather than failing the
    // build, so adopting them stays a deliberate refactor.
    files: ["**/*.{js,jsx,mjs,ts,tsx,mts,cts}"],
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
];

export default config;
