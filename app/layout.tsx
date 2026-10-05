import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import PostHogProvider from "@/components/analytics/PostHogProvider";
import VercelAnalytics from "@/components/analytics/VercelAnalytics";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://aipokerlab.com";

export const viewport: Viewport = {
  themeColor: "#059669",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "AI Poker Lab — The AI Poker Lab That Makes You Unbeatable",
    template: "%s | AI Poker Lab",
  },
  description:
    "GTO poker training SaaS that beats GTO Wizard by being a better COACH. Personalized AI explanations, leak-to-drill closed loop, adaptive learning. ToS-compliant training — not a bot.",
  keywords: [
    "ai poker bot",
    "ai poker lab",
    "gto poker trainer",
    "poker gto coach",
    "ai poker study tool",
    "gto wizard alternative",
    "poker training software",
    "gto solver",
    "poker leak detector",
    "preflop charts gto",
    "poker ai coach",
    "learn gto poker",
  ],
  authors: [{ name: "AI Poker Lab", url: SITE_URL }],
  creator: "AI Poker Lab",
  publisher: "AI Poker Lab",
  category: "Education",
  classification: "Poker Training Software",
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    title: "AI Poker Lab — The AI Poker Lab That Makes You Unbeatable",
    description:
      "Master GTO with an AI coach that explains WHY, finds your leaks, and drills you until you're unbeatable. ToS-compliant.",
    url: SITE_URL,
    siteName: "AI Poker Lab",
    type: "website",
    locale: "en_US",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "AI Poker Lab — GTO Training with AI Coach",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Poker Lab — The AI Poker Lab That Makes You Unbeatable",
    description:
      "GTO training with a real AI coach. Leak detection → personalized drills → measurable improvement.",
    images: ["/og-image.png"],
    creator: "@aipokerlab",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION || undefined,
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  manifest: "/manifest.webmanifest",
  other: {
    "google-adsense-account": process.env.GOOGLE_ADSENSE_ACCOUNT || "",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900">
        <PostHogProvider>{children}</PostHogProvider>
        <VercelAnalytics />
      </body>
    </html>
  );
}
