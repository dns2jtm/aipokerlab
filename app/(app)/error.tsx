"use client";

import { useEffect } from "react";
import { captureError } from "@/lib/monitoring/sentry";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    captureError(error, { digest: error.digest, scope: "app" });
  }, [error]);

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-xl">⚠️</div>
      <h2 className="mt-4 text-lg font-bold">Something went wrong</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600">
        We&apos;ve logged the error. Please try again or return to the dashboard.
      </p>
      {error.digest && <p className="mt-2 text-xs text-zinc-400">Error ID: {error.digest}</p>}
      <div className="mt-6 flex justify-center gap-3">
        <button
          onClick={() => reset()}
          className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-emerald-700"
        >
          Try again
        </button>
        <a href="/dashboard" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">
          Dashboard
        </a>
      </div>
    </div>
  );
}
