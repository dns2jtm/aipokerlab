# AI Poker Lab — aipokerlab.com

> **Lab, not bot.** ToS-compliant GTO poker training: AI coach, leak detection, and spaced-repetition drills. Post-hand study only — not for use during live play.

Beats GTO Wizard by being a better **coach**: explains WHY (blockers, MDF, equity realization), links every mistake to your leaks, and auto-generates drills until the leak is fixed.

## Tech Stack

- **Next.js 15** (App Router, RSC, Route Handlers) + **TypeScript strict** + **Tailwind CSS**
- **PostgreSQL** (Neon / Supabase) + **Prisma ORM**
- **Redis** (Upstash) — solver cache, rate limiting
- **Stripe** — subscriptions (Free / Starter $19 / Pro $49 / Elite $99), Customer Portal, webhooks
- **Native Rust 6-Max/HU Linear MCCFR & ReBeL Solver (`engine/noregrets` + `poker_lab.py`)** — Parallel Linear MCCFR blueprints with OCHS (Opponent-Cluster Hand Strength + EMD k-medians), VR-MCCFR control variates, ReBeL belief-state value networks (`valuenet.rs`), Burch safety-gadget continual resolving (`turn.rs`, `river.rs`, `ablate.rs`), expert-iteration distillation (`distill.rs`), AIVAT variance reduction (`aivat.rs`), and persistent `--stdio` JSON worker
- **PyTorch Belief-State Value Network & IR Drill Recommender (`value_net_torch.py` + `test_value_net_torch.py`)** — PyTorch (`torch.nn.Module`, `AdamW`, cosine annealing, range-weighted Huber/MSE loss) training pipeline exporting `bincode`/`VN01` weights (`value_net.bin`), hybrid lexical/embedding leak-to-drill recommender (`DrillRecommender`), and offline ranking & A/B policy evaluation (`NDCG@k`, `MRR`, `Precision@k`, `Recall@k`, `Brier`, Welch $t$-test with AIVAT control variates)
- **Python/NumPy CFR+ Restricted Subgame Solver (`showdown_solver.py` + `postflop.py`)** — Multi-sizing (`33%`, `66%`, `100%` pot), opponent reraise branches, IP/OOP equity-realization matrices, and exact NashConv (`solver_gap_chips`) measurement
- **Hybrid Web Solver (`lib/solver/`)** — pre-computed DB (90% hits, <50ms) + on-demand solver service
- **AI Coach** — OpenAI / Anthropic, Vercel AI SDK streaming, grounded in solver JSON (temp 0.3)
- **Vercel** — hosting, ISR, edge functions

## Architecture Overview

See [`SOLVER_LIMITS.md`](./SOLVER_LIMITS.md) for solver scope, architecture, and empirical benchmarks.

```
app/(marketing)/  → landing, about, methodology, pricing, contact, privacy, terms
app/(app)/        → dashboard, lab/preflop, replayer, leaks, drills, coach, billing
app/api/          → solve, parse, coach, drills, billing (checkout/portal/webhook)
lib/solver/       → TypeScript SolverService abstraction (Precomputed / TexasSolver / Mock)
engine/noregrets/ → Native Rust 6-Max/HU Linear MCCFR + ReBeL Subgame Resolver
poker_lab.py      → Python bridge & persistent stdio worker for engine/noregrets
showdown_solver.py→ Fast NumPy CFR+ restricted subgame solver with exact NashConv
lib/coach/        → promptComposer, coachEngine (grounded, leak-aware)
lib/leaks/        → 12 detectors + analyzer (bb/100, severity)
lib/drills/       → engine (leak → drill, spaced repetition)
lib/parser/       → PokerStars + GGPoker hand history parsers
lib/billing/      → plans, gating, Stripe helpers
prisma/           → schema (User, Hand, SolverCache, Leak, Drill, etc.)
components/       → replayer, drills, coach, marketing (AuthorBio)
```

**Key design decisions:**
- `spotHash` = deterministic hash of `board + ranges + stack + pot + betSizings + rake` → O(1) SolverCache lookup
- Dual-layer postflop/subgame solving: Native Rust `engine/noregrets` (OCHS + VR-MCCFR + ReBeL value networks + Burch safety gadget) paired with fast NumPy CFR+ (`showdown_solver.py`)
- Every `Drill` is generated FROM a `Leak` (closed loop)
- AI Coach is grounded: every response tied to `strategyMap + evMap + leak profile`, cached 7 days

## Solver Benchmarks (`SOLVER_LIMITS.md`)

- **Exploitability Reduction (`ochs-vr-v1` vs `local-v1`)**: Reduces exact turn/river best-response (`br`) exploitability lower bound by **42.5%** (`304.0` vs `528.5 BB/100`) and Local Best Response (`lbr`) bound by **11.9%** (`376.3` vs `427.0 BB/100`).
- **6-Max Cross-Play (24,000 hands)**: `distilled-v1` beats `ochs-vr-v1` by **+26.75 BB/100** and `local-v1` by **+40.57 BB/100**.
- **Burch Gadget Safe-Resolving Ablation**: Under maximally corrupted range beliefs (`ε = 1.0`), unsafe resolving exposes up to **317.4 chips** (`9.8` chips mean) of best-response exploitation beyond the blueprint safety value, whereas Burch gadget safe-resolving bounds the mean margin to **1.7 chips** (`< 0.1%` of the pot) and cuts worst-case combo exploitation by **86.5%** (`42.7` vs `317.4` chips).

## Getting Started

### Prerequisites

- Node 20+, npm
- Rust toolchain (`cargo`) & Python 3.11+ (for native solver & lab tests)
- Postgres (local or Neon/Supabase)
- Stripe account (optional for local — mocks gracefully)

### 1. Install

```bash
cd aipokerlab
npm install
```

### 2. Env

```bash
cp .env.example .env.local
# Fill in DATABASE_URL, STRIPE_*, OPENAI_API_KEY or ANTHROPIC_API_KEY, etc.
```

Required for full functionality:
- `DATABASE_URL` — Postgres connection string
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` — billing
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — AI Coach (falls back to mock if missing)
- `NEXT_PUBLIC_APP_URL` — e.g. `http://localhost:3000` locally, `https://aipokerlab.com` in prod

See `.env.example` for all vars.

### 3. Database

```bash
npx prisma migrate dev
npx prisma generate
# Optional: seed
npx prisma db seed
```

### 4. Run & Test

```bash
npm run dev
# → http://localhost:3000

# Run TypeScript unit tests
npm test

# Run Python solver & lab test suite
python3 -m pytest -q
```

- Marketing: `/`, `/about`, `/methodology`, `/pricing`, `/contact`, `/privacy`, `/terms`
- App: `/dashboard`, `/lab/preflop`, `/replayer`, `/leaks`, `/drills`, `/coach`, `/billing`
- SEO: `/sitemap.xml`, `/robots.txt`, `/manifest.webmanifest`

### 5. Build

```bash
npm run build
npm run start
```

## Deploy to Vercel

1. Push to GitHub.
2. Import project in Vercel — framework auto-detected as Next.js.
3. Add env vars in Vercel Dashboard → Settings → Environment Variables (copy from `.env.example`).
4. Set `NEXT_PUBLIC_APP_URL` to your production domain (e.g. `https://aipokerlab.com`).
5. Deploy. `vercel.json` handles security headers; `next.config.ts` handles image optimization.

**Stripe webhook:** In Stripe Dashboard → Webhooks, add `https://aipokerlab.com/api/billing/webhook` with events `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`. Copy signing secret to `STRIPE_WEBHOOK_SECRET`.

**Domain:** Add `aipokerlab.com` in Vercel → Domains, update DNS.

## SEO & E-E-A-T

- **Metadata:** `app/layout.tsx` has title template, description, keywords, openGraph, twitter, robots, canonical, verification
- **Sitemap:** `app/sitemap.ts` — marketing pages + 24 preflop lab URLs (6 positions × 4 stacks) + blog placeholders
- **Robots:** `app/robots.ts` — allow all, sitemap ref, disallow `/api/` and app routes
- **Manifest:** `app/manifest.ts` — PWA installability
- **JSON-LD:** Landing has SoftwareApplication, FAQPage, Organization, BreadcrumbList; pricing has Product + FAQ; methodology has TechArticle
- **E-E-A-T pages:** `/about` (founder story, team bios via `AuthorBio`), `/methodology` (solver validation vs PioSolver), `/pricing` (comparison vs GTO Wizard), `/contact` (mock form), `/privacy`, `/terms` (ToS-compliant training-only disclaimer)
- **Nav/Footer:** Marketing layout links all E-E-A-T pages, social, sitemap, ToS banner

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server (Turbopack) |
| `npm run build` | Production build |
| `npm run start` | Start production server |
| `npm run lint` | ESLint |
| `npm test` | Vitest suite |
| `python3 -m pytest -q` | Python CFR+ & Native Rust solver bridge tests |

## ToS Compliance

> **Training tool only — not for use during play. Compliant with PokerStars / GGPoker ToS. Post-hand study only.**

Lab does not connect to poker clients, read live tables, or provide real-time assistance. Using any solver or AI during live play violates platform ToS and risks bans/fund seizure. See `/terms` and `/about`.

## License

Private — all rights reserved.
