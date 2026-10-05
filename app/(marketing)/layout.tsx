import Link from "next/link";

const marketingNav = [
  { href: "/lab/preflop", label: "Preflop Lab" },
  { href: "/replayer", label: "Replayer" },
  { href: "/blog", label: "Blog" },
  { href: "/about", label: "About" },
  { href: "/methodology", label: "Methodology" },
  { href: "/pricing", label: "Pricing" },
  { href: "/contact", label: "Contact" },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-50 border-b border-zinc-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
              ♠
            </span>
            <span className="text-lg font-bold tracking-tight">
              aipokerlab<span className="text-emerald-600">.com</span>
            </span>
          </Link>
          <nav className="hidden items-center gap-5 text-sm font-medium text-zinc-600 md:flex">
            {marketingNav.map((n) => (
              <Link key={n.href} href={n.href} className="hover:text-zinc-900">
                {n.label}
              </Link>
            ))}
            <Link href="/dashboard" className="hover:text-zinc-900">
              Dashboard
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
            >
              Open Lab
            </Link>
          </div>
        </div>
        {/* Mobile nav */}
        <nav className="flex gap-3 overflow-x-auto border-t border-zinc-100 bg-white px-6 py-2 text-xs font-medium text-zinc-600 md:hidden">
          {marketingNav.map((n) => (
            <Link key={n.href} href={n.href} className="whitespace-nowrap hover:text-zinc-900">
              {n.label}
            </Link>
          ))}
        </nav>
        {/* ToS-compliant banner */}
        <div className="bg-amber-50 px-6 py-2 text-center text-xs font-medium text-amber-800">
          Training tool only — not for use during play. Compliant with PokerStars / GGPoker ToS. Post-hand study only.
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="grid gap-8 md:grid-cols-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                  ♠
                </span>
                <span className="text-sm font-bold">AI Poker Lab</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-zinc-600">
                ToS-compliant GTO training. Not a cheating bot. For post-hand study only.
              </p>
              <div className="mt-3 flex gap-2">
                <a
                  href="https://twitter.com/aipokerlab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-zinc-200 px-2.5 py-1 text-xs font-medium hover:bg-zinc-50"
                >
                  X
                </a>
                <a
                  href="https://github.com/aipokerlab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-zinc-200 px-2.5 py-1 text-xs font-medium hover:bg-zinc-50"
                >
                  GitHub
                </a>
                <a
                  href="https://www.youtube.com/@aipokerlab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-zinc-200 px-2.5 py-1 text-xs font-medium hover:bg-zinc-50"
                >
                  YouTube
                </a>
              </div>
            </div>
            <div>
              <h3 className="text-xs font-bold tracking-wide text-zinc-900">PRODUCT</h3>
              <ul className="mt-3 space-y-2 text-xs text-zinc-600">
                <li>
                  <Link href="/lab/preflop" className="hover:text-zinc-900 hover:underline">
                    Preflop Lab
                  </Link>
                </li>
                <li>
                  <Link href="/blog" className="hover:text-zinc-900 hover:underline">
                    Blog
                  </Link>
                </li>
                <li>
                  <Link href="/replayer" className="hover:text-zinc-900 hover:underline">
                    Replayer
                  </Link>
                </li>
                <li>
                  <Link href="/pricing" className="hover:text-zinc-900 hover:underline">
                    Pricing
                  </Link>
                </li>
                <li>
                  <Link href="/dashboard" className="hover:text-zinc-900 hover:underline">
                    Dashboard
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-bold tracking-wide text-zinc-900">COMPANY</h3>
              <ul className="mt-3 space-y-2 text-xs text-zinc-600">
                <li>
                  <Link href="/about" className="hover:text-zinc-900 hover:underline">
                    About
                  </Link>
                </li>
                <li>
                  <Link href="/methodology" className="hover:text-zinc-900 hover:underline">
                    Methodology
                  </Link>
                </li>
                <li>
                  <Link href="/contact" className="hover:text-zinc-900 hover:underline">
                    Contact
                  </Link>
                </li>
                <li>
                  <a href="mailto:hello@aipokerlab.com" className="hover:text-zinc-900 hover:underline">
                    hello@aipokerlab.com
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-bold tracking-wide text-zinc-900">LEGAL</h3>
              <ul className="mt-3 space-y-2 text-xs text-zinc-600">
                <li>
                  <Link href="/privacy" className="hover:text-zinc-900 hover:underline">
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link href="/terms" className="hover:text-zinc-900 hover:underline">
                    Terms of Service
                  </Link>
                </li>
                <li>
                  <Link href="/sitemap.xml" className="hover:text-zinc-900 hover:underline">
                    Sitemap
                  </Link>
                </li>
                <li>
                  <Link href="/robots.txt" className="hover:text-zinc-900 hover:underline">
                    Robots
                  </Link>
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-8 border-t border-zinc-200 pt-6 text-center text-xs text-zinc-500">
            <p>
              © {new Date().getFullYear()} AI Poker Lab — ToS-compliant GTO training. Not a cheating bot. For study
              only.
            </p>
            <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
              <strong>ToS Banner:</strong> Training tool only — not for use during play. Compliant with PokerStars /
              GGPoker ToS. Post-hand study only. Using solvers or AI during live play risks account bans and fund
              seizure.
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
