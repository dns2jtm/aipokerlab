export default function AppLoading() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 animate-pulse">
      <div className="h-8 w-48 rounded-lg bg-zinc-200" />
      <div className="h-4 w-96 rounded bg-zinc-100" />
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-zinc-200 bg-white p-5">
            <div className="h-4 w-24 rounded bg-zinc-200" />
            <div className="mt-3 h-6 w-16 rounded bg-zinc-100" />
            <div className="mt-2 h-3 w-full rounded bg-zinc-100" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <div className="h-4 w-32 rounded bg-zinc-200" />
        <div className="mt-4 grid grid-cols-13 gap-0.5">
          {Array.from({ length: 169 }).map((_, i) => (
            <div key={i} className="aspect-square rounded-sm bg-zinc-100" />
          ))}
        </div>
      </div>
    </div>
  );
}
