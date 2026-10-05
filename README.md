# AI Poker Lab — aipokerlab.com

> **Lab, not bot.** ToS-compliant GTO poker training: AI coach, leak detection, and spaced-repetition drills. Post-hand study only — not for use during live play.

Beats GTO Wizard by being a better **coach**: explains WHY (blockers, MDF, equity realization), links every mistake to your leaks, and auto-generates drills until the leak is fixed.

## Tech Stack

- **Next.js 15** (App Router, RSC, Route Handlers) + **TypeScript strict** + **Tailwind CSS**
- **PostgreSQL** (Neon / Supabase) + **Prisma ORM**
- **Redis** (Upstash) — solver cache, rate limiting
- **Stripe** — subscriptions (Free / Starter $19 / Pro $49 / Elite $99), Customer Portal, webhooks
- **Hybrid Solver** — pre-computed DB (90% hits, &lt;50ms) + on-demand TexasSolver/PioSolver worker
- **AI Coach** — OpenAI / Anthropic, Vercel AI SDK streaming, grounded in solver JSON (temp 0.3)
- **Vercel** — hosting, ISR, edge functions

## Architecture Overview

See [`plans/aipokerlab-architecture.md`](../plans/aipokerlab-architecture.md) for full system design.

```
app/(marketing)/  → landing, about, methodology, pricing, contact, privacy, terms
app/(app)/        → dashboard, lab/preflop, replayer, leaks, drills, coach, billing
app/api/          → solve, parse, coach, drills, billing (checkout/portal/webhook)
lib/solver/       → SolverService abstraction (Precomputed / TexasSolver / Mock)
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
- Every `Drill` is generated FROM a `Leak` (closed loop)
- AI Coach is grounded: every response tied to `strategyMap + evMap + leak profile`, cached 7 days

## Getting Started

### Prerequisites

- Node 20+, npm
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

### 4. Run

```bash
npm run dev
# → http://localhost:3000
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

## ToS Compliance

> **Training tool only — not for use during play. Compliant with PokerStars / GGPoker ToS. Post-hand study only.**

Lab does not connect to poker clients, read live tables, or provide real-time assistance. Using any solver or AI during live play violates platform ToS and risks bans/fund seizure. See `/terms` and `/about`.

## License

Private — all rights reserved.
