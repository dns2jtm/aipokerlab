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
    name: "Alex Rivera",
    role: "Co-founder & Head Coach",
    credentials: "500k+ hands · 5.2 bb/100 · GTO Wizard Certified · 2x WSOP Circuit Final Table",
    bio: "Alex spent 8 years as a mid-stakes 6-max reg before building Lab. He solved 30k+ spots with PioSolver and TexasSolver to build our pre-computed DB. Every coaching prompt is reviewed against his hand database.",
    initials: "AR",
    accent: "bg-emerald-600",
    imageAlt: "Alex Rivera — poker coach and co-founder",
    links: [
      { label: "Hendrix", href: "#" },
      { label: "TwoPlusTwo", href: "#" },
    ],
  },
  {
    name: "Dr. Priya Chen",
    role: "Co-founder & AI Research Lead",
    credentials: "PhD Machine Learning, Stanford · Ex-DeepMind · 3 papers on game-theoretic RL",
    bio: "Priya built the hybrid solver pipeline and the grounded coaching engine. Her research on exploitability-bounded solving keeps Lab's AI honest — every explanation is tied to solver JSON, never hallucinated.",
    initials: "PC",
    accent: "bg-violet-600",
    imageAlt: "Dr. Priya Chen — AI research lead and co-founder",
    links: [
      { label: "Google Scholar", href: "#" },
      { label: "arXiv", href: "#" },
    ],
  },
  {
    name: "Marcus Cole",
    role: "Lead Solver Engineer",
    credentials: "Ex-PioSolver contributor · 10 years C++ solver dev · TexasSolver integration",
    bio: "Marcus maintains the solver abstraction layer and nightly batch pipeline. He validates every pre-computed spot against PioSolver within 1% frequency delta.",
    initials: "MC",
    accent: "bg-zinc-800",
    imageAlt: "Marcus Cole — solver engineer",
  },
];

export function AuthorBio({ author }: { author: Author }) {
  return (
    <div className="flex gap-4 rounded-xl border border-zinc-200 bg-white p-5">
      <div
        className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${author.accent}`}
        aria-label={author.imageAlt}
        role="img"
      >
        {author.initials}
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-bold">{author.name}</h3>
        <p className="text-xs font-semibold text-emerald-700">{author.role}</p>
        <p className="mt-1 text-xs leading-4 text-zinc-500">{author.credentials}</p>
        <p className="mt-2 text-sm leading-6 text-zinc-600">{author.bio}</p>
        {author.links && (
          <div className="mt-2 flex gap-3 text-xs">
            {author.links.map((l) => (
              <Link key={l.label} href={l.href} className="font-medium text-zinc-500 underline hover:text-zinc-700">
                {l.label}
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
