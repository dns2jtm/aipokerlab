import Link from "next/link";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/lab/preflop", label: "Preflop Lab" },
  { href: "/replayer", label: "Replayer" },
  { href: "/leaks", label: "Leak Detector" },
  { href: "/drills", label: "IR Drills" },
  { href: "/coach", label: "AI Coach" },
  { href: "/methodology", label: "Solver Specs" },
  { href: "/billing", label: "Billing" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-r border-zinc-200 bg-white md:flex md:flex-col">
        <div className="flex h-14 items-center justify-between border-b border-zinc-200 px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
              ♠
            </span>
            <span className="text-sm font-bold">AI Poker Lab</span>
          </Link>
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-700">
            v2.4
          </span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-900"
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto space-y-2.5 border-t border-zinc-200 p-3">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-[11px] leading-4 text-zinc-600">
            <div className="font-mono font-bold text-zinc-900">ENGINE STATUS</div>
            <div className="mt-1 flex items-center gap-1.5 text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>O(1) spotHash + Rust MCCFR</span>
            </div>
            <div className="mt-0.5 text-zinc-500">15.96M+ infosets · VN01</div>
          </div>
          <div className="rounded-lg bg-amber-50 p-2.5 text-[11px] leading-4 text-amber-800">
            <strong>ToS Notice:</strong> Post-hand training only. Not for live play.
          </div>
          <div className="flex items-center justify-between px-1 text-xs text-zinc-500">
            <Link href="/" className="font-medium hover:text-zinc-800">
              ← Home
            </Link>
            <a
              href="https://github.com/dns2jtm/aipokerlab"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium hover:text-zinc-800"
            >
              GitHub ↗
            </a>
          </div>
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4 md:hidden">
          <Link href="/" className="text-sm font-bold">
            AI Poker Lab
          </Link>
          <nav className="flex gap-1.5 overflow-x-auto text-xs">
            {nav.slice(0, 5).map((n) => (
              <Link key={n.href} href={n.href} className="whitespace-nowrap rounded bg-zinc-100 px-2 py-1 font-medium">
                {n.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1 bg-zinc-50 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
