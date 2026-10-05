import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — How We Handle Your Data",
  description:
    "AI Poker Lab privacy policy: what we collect, how we use it, hand history privacy, no model training without opt-in, your rights, and contact.",
  alternates: { canonical: "https://aipokerlab.com/privacy" },
  openGraph: {
    title: "Privacy Policy — AI Poker Lab",
    url: "https://aipokerlab.com/privacy",
    type: "website",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "Privacy Policy", item: "https://aipokerlab.com/privacy" },
  ],
};

export default function PrivacyPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-3xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Privacy Policy
        </nav>

        <h1 className="text-3xl font-extrabold tracking-tight">Privacy Policy</h1>
        <p className="mt-2 text-xs text-zinc-500">Effective: October 1, 2025 · Last updated: October 5, 2025</p>

        <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">
          <strong>TL;DR:</strong> Your hand histories are yours. We never train models on your hands without explicit
          opt-in. You can delete everything at any time. We collect only what we need to run the Lab.
        </div>

        <div className="prose prose-zinc mt-8 max-w-none prose-sm prose-headings:font-bold prose-a:text-emerald-700">
          <h2>1. Who We Are</h2>
          <p>
            AI Poker Lab (&quot;Lab&quot;, &quot;we&quot;, &quot;us&quot;) is a ToS-compliant GTO poker training
            platform at <Link href="/">aipokerlab.com</Link>. Contact:{" "}
            <a href="mailto:hello@aipokerlab.com">hello@aipokerlab.com</a> /{" "}
            <a href="mailto:privacy@aipokerlab.com">privacy@aipokerlab.com</a>.
          </p>

          <h2>2. What We Collect</h2>
          <ul>
            <li>
              <strong>Account data:</strong> email, name, image (via auth provider), subscription tier, Stripe customer
              ID.
            </li>
            <li>
              <strong>Hand histories &amp; hands:</strong> raw text you upload, parsed JSON, stakes/format, hero cards,
              actions, board, results. Stored per-user, isolated.
            </li>
            <li>
              <strong>Usage &amp; product data:</strong> leaks, drills, drill attempts, progress (level, streak, XP),
              coaching sessions (prompt, solver context, LLM response, tokens), feedback.
            </li>
            <li>
              <strong>Technical:</strong> IP, user agent, cookies/localStorage for auth and preferences, analytics
              (PostHog / Vercel Analytics) if enabled.
            </li>
            <li>
              <strong>Payments:</strong> processed by Stripe. We never store full card numbers.
            </li>
          </ul>

          <h2>3. How We Use It</h2>
          <ul>
            <li>Provide the Lab: parsing, solver lookups, leak detection, drills, AI coaching.</li>
            <li>Personalize coaching (leak-aware, tone adaptation, spaced repetition).</li>
            <li>Billing, subscription management, and support.</li>
            <li>Product improvement and analytics (aggregated, not per-hand without consent).</li>
            <li>Security, fraud prevention, and ToS enforcement.</li>
          </ul>

          <h2>4. Hand History Privacy — No Training Without Opt-In</h2>
          <p>
            <strong>Your hands never train our models without explicit opt-in.</strong> Raw histories are stored
            encrypted (R2 + Postgres), parsed hands are isolated per user, and embeddings (if used for similarity
            search) are per-user unless you opt into aggregated research. You can request deletion of all hand data at
            any time via <a href="mailto:privacy@aipokerlab.com">privacy@aipokerlab.com</a> or in-app (when available).
          </p>

          <h2>5. AI Coach &amp; LLM Data</h2>
          <p>
            Coaching requests send solver context + leak summary + anonymized hand snippet to our LLM provider (OpenAI /
            Anthropic) for inference only. We cache responses by hash(solverContext + leakId) for 7 days to reduce cost
            — many users share spots. We do not use your prompts to fine-tune models without opt-in. See{" "}
            <Link href="/methodology">Methodology</Link> for grounding details.
          </p>

          <h2>6. Sharing &amp; Processors</h2>
          <ul>
            <li>
              <strong>Processors:</strong> Vercel (hosting), Neon/Supabase (Postgres), Upstash (Redis), Cloudflare R2
              (storage), Stripe (payments), OpenAI/Anthropic (LLM inference), PostHog/Vercel Analytics (analytics),
              Resend (email).
            </li>
            <li>We do not sell your personal data.</li>
            <li>We share only as needed to provide the service or as required by law.</li>
          </ul>

          <h2>7. Retention</h2>
          <ul>
            <li>Account &amp; subscription: while account is active + 30 days after deletion (for recovery).</li>
            <li>Hand histories &amp; hands: until you delete them or delete your account.</li>
            <li>SolverCache: shared, not per-user; LRU eviction.</li>
            <li>Coaching sessions: until account deletion or per your request.</li>
          </ul>

          <h2>8. Your Rights</h2>
          <p>
            Depending on your jurisdiction (GDPR, CCPA, etc.), you may have rights to access, correct, delete, port,
            or object to processing. Contact <a href="mailto:privacy@aipokerlab.com">privacy@aipokerlab.com</a>. We
            respond within 30 days.
          </p>

          <h2>9. Cookies</h2>
          <p>
            We use essential cookies for auth and preferences, and analytics cookies if you consent (where required).
            You can control cookies via browser settings; essential cookies are required for login.
          </p>

          <h2>10. Security</h2>
          <p>
            HTTPS everywhere, encrypted storage, least-privilege access, and regular dependency updates. No system is
            100% secure — we disclose breaches as required by law.
          </p>

          <h2>11. Children</h2>
          <p>Lab is not for users under 18. We do not knowingly collect data from children.</p>

          <h2>12. International Transfers</h2>
          <p>
            Data may be processed in the US and other regions where our processors operate. We use standard contractual
            clauses where required.
          </p>

          <h2>13. Changes</h2>
          <p>
            We&apos;ll update this page and, for material changes, notify via email or in-app. Continued use after
            changes means acceptance.
          </p>

          <h2>14. Contact</h2>
          <p>
            Privacy questions: <a href="mailto:privacy@aipokerlab.com">privacy@aipokerlab.com</a> · General:{" "}
            <a href="mailto:hello@aipokerlab.com">hello@aipokerlab.com</a> ·{" "}
            <Link href="/contact">Contact form</Link>
          </p>
        </div>

        <div className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs leading-5 text-zinc-600">
          This is a template privacy policy for an MVP. Have counsel review before handling real user data at scale.
          Not legal advice.
        </div>

        <p className="mt-6 text-xs text-zinc-500">
          See also:{" "}
          <Link href="/terms" className="underline">
            Terms of Service
          </Link>{" "}
          ·{" "}
          <Link href="/about" className="underline">
            About
          </Link>{" "}
          ·{" "}
          <Link href="/methodology" className="underline">
            Methodology
          </Link>
        </p>
      </div>
    </>
  );
}
