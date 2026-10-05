import Link from "next/link";

export default function MarketingNotFound() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-emerald-600">404</p>
      <h1 className="mt-2 text-3xl font-extrabold tracking-tight">Page not found</h1>
      <p className="mt-3 text-sm leading-6 text-zinc-600">
        The page you are looking for does not exist. Try the Preflop Lab or head back home.
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/" className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-bold text-white hover:bg-zinc-800">
          Back to home
        </Link>
        <Link href="/lab/preflop" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">
          Preflop Lab
        </Link>
      </div>
    </div>
  );
}
