export default function MarketingLoading() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-12 animate-pulse">
      <div className="grid gap-10 md:grid-cols-2">
        <div className="space-y-4">
          <div className="h-4 w-40 rounded-full bg-zinc-200" />
          <div className="h-10 w-3/4 rounded-lg bg-zinc-200" />
          <div className="h-10 w-2/3 rounded-lg bg-zinc-200" />
          <div className="h-20 w-full rounded-lg bg-zinc-100" />
          <div className="flex gap-3">
            <div className="h-10 w-32 rounded-full bg-zinc-200" />
            <div className="h-10 w-32 rounded-full bg-zinc-100" />
          </div>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-4">
          <div className="mb-3 h-4 w-32 rounded bg-zinc-200" />
          <div className="grid grid-cols-13 gap-0.5">
            {Array.from({ length: 169 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-sm bg-zinc-100" />
            ))}
          </div>
        </div>
      </div>
      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-zinc-200 bg-white p-6">
            <div className="h-6 w-6 rounded bg-zinc-200" />
            <div className="mt-3 h-4 w-3/4 rounded bg-zinc-200" />
            <div className="mt-2 h-16 w-full rounded bg-zinc-100" />
          </div>
        ))}
      </div>
    </div>
  );
}
