import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service — Training Only, ToS-Compliant",
  description:
    "AI Poker Lab Terms of Service: training-only, no real-money bot usage, no live-play assistance, subscriptions, refunds, and acceptable use.",
  alternates: { canonical: "https://aipokerlab.com/terms" },
  openGraph: {
    title: "Terms of Service — AI Poker Lab",
    url: "https://aipokerlab.com/terms",
    type: "website",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "Terms of Service", item: "https://aipokerlab.com/terms" },
  ],
};

export default function TermsPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-3xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Terms of Service
        </nav>

        <h1 className="text-3xl font-extrabold tracking-tight">Terms of Service</h1>
        <p className="mt-2 text-xs text-zinc-500">Effective: October 1, 2025 · Last updated: October 5, 2025</p>

        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
          <strong>Training-only disclaimer:</strong> AI Poker Lab is a <strong>training tool for post-hand study only</strong>.
          It must not be used during live play. Real-time solver or AI assistance violates the Terms of Service of
          PokerStars, GGPoker, and other platforms and risks account bans and fund seizure. Lab is <strong>not</strong>{" "}
          a cheating bot and does not play poker for you.
        </div>

        <div className="prose prose-zinc mt-8 max-w-none prose-sm prose-headings:font-bold prose-a:text-emerald-700">
          <h2>1. Acceptance</h2>
          <p>
            By accessing <Link href="/">aipokerlab.com</Link> or using the Lab (including Preflop Lab, Replayer, Leak
            Detector, Drills, AI Coach, and related APIs), you agree to these Terms and our{" "}
            <Link href="/privacy">Privacy Policy</Link>. If you don&apos;t agree, don&apos;t use the service.
          </p>

          <h2>2. What Lab Is (and Is Not)</h2>
          <ul>
            <li>
              <strong>Lab is:</strong> a study tool that helps you review past hands, understand GTO, find leaks, and
              drill. All coaching is post-hand.
            </li>
            <li>
              <strong>Lab is not:</strong> a bot, real-time assistant (RTA), or automated player. It does not connect
              to poker clients, read live tables, or make decisions during play.
            </li>
            <li>
              <strong>You are responsible</strong> for complying with the ToS of any poker platform you play on. Using
              any solver or AI during live play — including Lab — may violate those ToS.
            </li>
          </ul>

          <h2>3. Eligibility</h2>
          <p>
            You must be at least 18 years old and legally allowed to use poker training software in your jurisdiction.
            Lab is for educational purposes; it does not facilitate real-money gambling.
          </p>

          <h2>4. Accounts</h2>
          <ul>
            <li>You are responsible for your account and for keeping credentials secure.</li>
            <li>One account per person; don&apos;t share or resell access.</li>
            <li>We may suspend accounts that violate these Terms or abuse the service.</li>
          </ul>

          <h2>5. Acceptable Use</h2>
          <p>You agree not to:</p>
          <ul>
            <li>Use Lab during live play or as real-time assistance (RTA).</li>
            <li>Automate play, scrape solver outputs at scale to build a bot, or reverse-engineer the solver DB.</li>
            <li>Upload hand histories you don&apos;t have rights to, or that contain others&apos; personal data without consent.</li>
            <li>Abuse rate limits, bypass paywalls, or interfere with the service.</li>
            <li>Use the AI Coach to generate advice for live play.</li>
          </ul>

          <h2>6. Subscriptions, Billing &amp; Refunds</h2>
          <ul>
            <li>
              Plans: Free, Starter ($19/mo), Pro ($49/mo), Elite ($99/mo). Prices USD, billed monthly via Stripe.
            </li>
            <li>Manage or cancel anytime via Stripe Customer Portal at /billing. Cancellation takes effect at period end.</li>
            <li>
              Refunds: if you believe you were charged in error, contact{" "}
              <a href="mailto:hello@aipokerlab.com">hello@aipokerlab.com</a> within 14 days. We review case by case.
              No refunds for partial months after use.
            </li>
            <li>We may change pricing with 30 days&apos; notice; continued use means acceptance.</li>
          </ul>

          <h2>7. Solver &amp; Coaching — No Guarantees</h2>
          <ul>
            <li>
              Solver outputs are based on abstractions (2–3 sizings, 0.5% exploitability, rake 5% cap $3) and are
              validated vs PioSolver within ~1% frequency delta — but they are not perfect GTO and not financial or
              gambling advice.
            </li>
            <li>
              AI coaching is grounded in solver JSON (temperature 0.3, 800 tokens) but may contain errors. Always
              cross-check with solver data and your own study. See <Link href="/methodology">Methodology</Link>.
            </li>
            <li>We do not guarantee win rates, bb/100 improvement, or any poker results.</li>
          </ul>

          <h2>8. Intellectual Property</h2>
          <p>
            Lab&apos;s software, solver DB, coaching prompts, and content are owned by AI Poker Lab or its licensors.
            Your hand histories and feedback remain yours; you grant us a license to process them to provide the
            service. Aggregated, anonymized data may be used for product improvement.
          </p>

          <h2>9. Privacy</h2>
          <p>
            See <Link href="/privacy">Privacy Policy</Link>. Key point: your hands never train our models without
            explicit opt-in. You can delete your data at any time.
          </p>

          <h2>10. Disclaimers</h2>
          <p>
            Lab is provided &quot;as is&quot; without warranties. We disclaim all implied warranties to the fullest
            extent allowed by law. Lab is not affiliated with PokerStars, GGPoker, GTO Wizard, PioSolver, or
            TexasSolver.
          </p>

          <h2>11. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by law, AI Poker Lab&apos;s liability is limited to the amount you paid in
            the 12 months before the claim. We are not liable for indirect, incidental, or consequential damages,
            including poker losses, account bans, or fund seizures from misuse.
          </p>

          <h2>12. Indemnification</h2>
          <p>
            You agree to indemnify and hold harmless AI Poker Lab from claims arising from your misuse of the service,
            violation of these Terms, or violation of any poker platform&apos;s ToS.
          </p>

          <h2>13. Termination</h2>
          <p>
            We may suspend or terminate access for violations, non-payment, or legal reasons. You may delete your
            account at any time. Sections that should survive (IP, disclaimers, liability limits) do survive.
          </p>

          <h2>14. Governing Law</h2>
          <p>
            These Terms are governed by the laws of the State of Delaware, USA, without regard to conflict-of-law
            rules. Disputes will be resolved in the courts of Delaware, unless otherwise required by law.
          </p>

          <h2>15. Changes</h2>
          <p>
            We may update these Terms. For material changes, we&apos;ll notify via email or in-app and update the
            effective date. Continued use after changes means acceptance.
          </p>

          <h2>16. Contact</h2>
          <p>
            Questions: <a href="mailto:hello@aipokerlab.com">hello@aipokerlab.com</a> · Legal:{" "}
            <a href="mailto:legal@aipokerlab.com">legal@aipokerlab.com</a> ·{" "}
            <Link href="/contact">Contact form</Link>
          </p>
        </div>

        <div className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs leading-5 text-zinc-600">
          This is a template Terms of Service for an MVP. Have counsel review before handling real users and payments.
          Not legal advice.
        </div>

        <p className="mt-6 text-xs text-zinc-500">
          See also:{" "}
          <Link href="/privacy" className="underline">
            Privacy Policy
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
