import Link from "next/link";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/lab/preflop", label: "Preflop Lab" },
  { href: "/replayer", label: "Replayer" },
  { href: "/leaks", label: "Leaks" },
  { href: "/drills", label: "Drills" },
  { href: "/coach", label: "AI Coach" },
  { href: "/billing", label: "Billing" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 border-r border-zinc-200 bg-white md:flex md:flex-col">
        <div className="flex h-14 items-center gap-2 border-b border-zinc-200 px-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
            ♠
          </span>
          <span className="text-sm font-bold">AI Poker Lab</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto border-t border-zinc-200 p-3">
          <div className="rounded-lg bg-amber-50 p-3 text-xs leading-4 text-amber-800">
            <strong>ToS Notice:</strong> Training only. Not for use during play.
          </div>
          <Link
            href="/"
            className="mt-3 block text-center text-xs font-medium text-zinc-500 hover:text-zinc-700"
          >
            ← Back to site
          </Link>
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4 md:hidden">
          <span className="text-sm font-bold">AI Poker Lab</span>
          <nav className="flex gap-2 text-xs">
            {nav.slice(0, 4).map((n) => (
              <Link key={n.href} href={n.href} className="rounded bg-zinc-100 px-2 py-1">
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
