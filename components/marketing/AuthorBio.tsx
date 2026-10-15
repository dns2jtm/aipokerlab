import Link from "next/link";

export interface Author {
  name: string;
  role: string;
  credentials: string;
  bio: string;
  imageAlt: string;
  initials: string;
  accent: string;
  links?: { label: string; href: string }[];
}

export const AUTHORS: Author[] = [
  {
    name: "Daniel Sawa",
    role: "Founder & Lead Systems / ML Engineer",
    credentials:
      "BSc (Hons) Computer Science · University of York · Systems, Quantitative Modeling & Imperfect-Information Game Theory",
    bio: "Daniel architected AI Poker Lab from first principles—building the multi-threaded Rust 6-Max & Heads-Up Linear MCCFR solver (15.96M+ infosets, VR-MCCFR control variates, OCHS L1/EMD clustering), the PyTorch ReBeL belief-state value network (VN01), Burch safety-gadget continual resolving, the vectorized Python/NumPy CFR+ restricted subgame solver, and the Next.js 15 / TypeScript / Redis training & IR drill recommendation platform.",
    initials: "DS",
    accent: "bg-emerald-600",
    imageAlt: "Daniel Sawa — Founder & Lead Systems / ML Engineer",
    links: [
      { label: "GitHub (@dns2jtm)", href: "https://github.com/dns2jtm" },
      { label: "Repository", href: "https://github.com/dns2jtm/aipokerlab" },
      { label: "Solver Architecture & Benchmarks", href: "/methodology" },
    ],
  },
];

export function AuthorBio({ author }: { author: Author }) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:flex-row">
      <div
        className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-base font-extrabold text-white shadow-sm ${author.accent}`}
        aria-label={author.imageAlt}
        role="img"
      >
        {author.initials}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-bold text-zinc-900">{author.name}</h3>
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
            {author.role}
          </span>
        </div>
        <p className="mt-1 text-xs font-medium leading-5 text-zinc-500">{author.credentials}</p>
        <p className="mt-2.5 text-sm leading-6 text-zinc-600">{author.bio}</p>
        {author.links && (
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            {author.links.map((l) => (
              <Link
                key={l.label}
                href={l.href}
                target={l.href.startsWith("http") ? "_blank" : undefined}
                rel={l.href.startsWith("http") ? "noopener noreferrer" : undefined}
                className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 font-semibold text-zinc-700 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-800"
              >
                {l.label} →
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AuthorBios({ authors = AUTHORS }: { authors?: Author[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-1">
      {authors.map((a) => (
        <AuthorBio key={a.name} author={a} />
      ))}
    </div>
  );
}
