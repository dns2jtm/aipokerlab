import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AI Poker Lab — GTO Training with AI Coach",
    short_name: "AI Poker Lab",
    description:
      "GTO poker training with AI coach, leak detection, and spaced-repetition drills. ToS-compliant post-hand study.",
    start_url: "/",
    display: "standalone",
    background_color: "#fafafa",
    theme_color: "#059669",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
    ],
    categories: ["education", "games", "sports"],
    lang: "en",
    dir: "ltr",
    orientation: "any",
  };
}
