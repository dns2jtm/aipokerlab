import Link from "next/link";

export default function AppNotFound() {
  return (
    <div className="mx-auto max-w-2xl py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-emerald-600">404</p>
      <h1 className="mt-2 text-3xl font-extrabold tracking-tight">Not found</h1>
      <p className="mt-3 text-sm leading-6 text-zinc-600">This Lab page does not exist. Return to the dashboard.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/dashboard" className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-bold text-white hover:bg-zinc-800">
          Dashboard
        </Link>
        <Link href="/" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">
          Home
        </Link>
      </div>
    </div>
  );
}
