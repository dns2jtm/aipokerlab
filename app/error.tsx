"use client";

import { useEffect } from "react";
import { captureError } from "@/lib/monitoring/sentry";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    captureError(error, { digest: error.digest, scope: "global" });
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen flex items-center justify-center bg-zinc-50 p-6">
        <div className="max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-xl">⚠️</div>
          <h2 className="mt-4 text-lg font-bold">Something went wrong</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            We&apos;ve logged the error and will look into it. Please try again or go back to the homepage.
          </p>
          {error.digest && <p className="mt-2 text-xs text-zinc-400">Error ID: {error.digest}</p>}
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={() => reset()}
              className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-emerald-700"
            >
              Try again
            </button>
            <a href="/" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">
              Go home
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
