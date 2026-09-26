import type { MetadataRoute } from "next";

/** Makes Fareeq installable: its own window, icon and shortcuts. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Fareeq — Personal AI Team",
    short_name: "Fareeq",
    description: "Leo, your personal assistant, plus a team of specialists that share your context.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#FFF7DF",
    theme_color: "#FFF7DF",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
    shortcuts: [
      { name: "Talk to Leo", short_name: "Leo", url: "/agents/modeer" },
      { name: "Your plans", short_name: "Plans", url: "/plans" },
      { name: "Your week", short_name: "Week", url: "/week" },
    ],
  };
}
