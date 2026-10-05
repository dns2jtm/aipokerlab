import type { Metadata } from "next";
import Link from "next/link";
import ContactForm from "./ContactForm";

export const metadata: Metadata = {
  title: "Contact — Get in Touch with AI Poker Lab",
  description:
    "Contact AI Poker Lab: hello@aipokerlab.com. Support, billing, methodology questions, or just say hi. We reply within 24 hours.",
  alternates: { canonical: "https://aipokerlab.com/contact" },
  openGraph: {
    title: "Contact AI Poker Lab",
    description: "Questions about Lab, billing, or methodology? Reach us at hello@aipokerlab.com.",
    url: "https://aipokerlab.com/contact",
    type: "website",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "Contact", item: "https://aipokerlab.com/contact" },
  ],
};

const contactJsonLd = {
  "@context": "https://schema.org",
  "@type": "ContactPage",
  name: "Contact AI Poker Lab",
  url: "https://aipokerlab.com/contact",
  mainEntity: {
    "@type": "Organization",
    name: "AI Poker Lab",
    url: "https://aipokerlab.com",
    email: "hello@aipokerlab.com",
    contactPoint: {
      "@type": "ContactPoint",
      email: "hello@aipokerlab.com",
      contactType: "customer support",
      availableLanguage: ["English"],
    },
    sameAs: [
      "https://twitter.com/aipokerlab",
      "https://github.com/aipokerlab",
      "https://www.youtube.com/@aipokerlab",
    ],
  },
};

export default function ContactPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(contactJsonLd) }} />

      <div className="mx-auto max-w-4xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Contact
        </nav>

        <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">Contact</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">
          Questions about Lab, billing, methodology, or just want to say hi? We reply within 24 hours.
        </p>

        <div className="mt-8 grid gap-8 md:grid-cols-5">
          <div className="md:col-span-3">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6">
              <h2 className="text-sm font-bold">Send a message</h2>
              <p className="mt-1 text-xs text-zinc-500">Mock form — no backend yet. Submits locally with confirmation.</p>
              <div className="mt-4">
                <ContactForm />
              </div>
            </div>
          </div>

          <div className="space-y-4 md:col-span-2">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6">
              <h2 className="text-sm font-bold">Direct contact</h2>
              <div className="mt-3 space-y-3 text-sm">
                <div>
                  <div className="text-xs font-semibold tracking-wide text-zinc-500">EMAIL</div>
                  <a href="mailto:hello@aipokerlab.com" className="font-medium text-emerald-700 underline">
                    hello@aipokerlab.com
                  </a>
                </div>
                <div>
                  <div className="text-xs font-semibold tracking-wide text-zinc-500">SUPPORT HOURS</div>
                  <div className="text-zinc-600">Mon–Fri, 9am–6pm PT · 24h response</div>
                </div>
                <div>
                  <div className="text-xs font-semibold tracking-wide text-zinc-500">BILLING</div>
                  <div className="text-zinc-600">
                    Manage subscription at{" "}
                    <Link href="/billing" className="underline">
                      /billing
                    </Link>{" "}
                    (Stripe Customer Portal)
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6">
              <h2 className="text-sm font-bold">Social</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  { label: "X / Twitter", href: "https://twitter.com/aipokerlab" },
                  { label: "GitHub", href: "https://github.com/aipokerlab" },
                  { label: "YouTube", href: "https://www.youtube.com/@aipokerlab" },
                  { label: "Discord", href: "#" },
                ].map((s) => (
                  <a
                    key={s.label}
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-full border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50"
                  >
                    {s.label}
                  </a>
                ))}
              </div>
              <p className="mt-3 text-xs text-zinc-500">Follow for leak-fix threads, solver deep dives, and product updates.</p>
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
              <strong>ToS reminder:</strong> Lab is for post-hand study only. Don&apos;t use during live play. See{" "}
              <Link href="/terms" className="underline">
                Terms
              </Link>
              .
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
