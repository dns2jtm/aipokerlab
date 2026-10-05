type Severity = "fatal" | "error" | "warning" | "info" | "debug";

type SentryContext = Record<string, unknown>;

// Dynamic import helper — uses Function to avoid static analysis by Next.js bundler
async function tryLoadSentry(): Promise<{
  captureException: (err: unknown, ctx?: unknown) => string | undefined;
  captureMessage: (msg: string, level?: string) => string | undefined;
  withScope: (cb: (scope: unknown) => void) => void;
} | null> {
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return null;
  try {
    // Use eval to hide from bundler static analysis
    const mod = await (0, eval)('import("@sentry/nextjs")');
    return mod as unknown as {
      captureException: (err: unknown, ctx?: unknown) => string | undefined;
      captureMessage: (msg: string, level?: string) => string | undefined;
      withScope: (cb: (scope: unknown) => void) => void;
    };
  } catch {
    return null;
  }
}

export function captureError(error: unknown, context?: SentryContext): string | undefined {
  const dsn = process.env.SENTRY_DSN;
  if (dsn) {
    void tryLoadSentry().then((mod) => {
      if (mod) {
        try {
          mod.captureException(error, context ? { extra: context, level: "error" } : undefined);
        } catch {
          // ignore
        }
      }
    });
    // Also log in mock mode for visibility
    if (!process.env.NEXT_RUNTIME || process.env.NODE_ENV === "development") {
      const msg = error instanceof Error ? error.message : String(error);
      console.error(`[Sentry] captureError: ${msg}`, context || "");
    }
    return undefined;
  }
  const msg = error instanceof Error ? error.message : String(error);
  const stack = error instanceof Error ? error.stack : undefined;
  console.error(`[Sentry mock] captureError: ${msg}`, { context, stack: stack?.slice(0, 500) });
  return undefined;
}

export function captureMessage(message: string, level: Severity = "info", context?: SentryContext): string | undefined {
  const dsn = process.env.SENTRY_DSN;
  if (dsn) {
    void tryLoadSentry().then((mod) => {
      if (mod) {
        try {
          mod.captureMessage(message, level);
        } catch {
          // ignore
        }
      }
    });
    return undefined;
  }
  console.log(`[Sentry mock] captureMessage [${level}]: ${message}`, context || "");
  return undefined;
}

export function withScope(callback: (scope: { setExtra: (key: string, value: unknown) => void; setLevel: (level: Severity) => void }) => void): void {
  const dsn = process.env.SENTRY_DSN;
  if (dsn) {
    void tryLoadSentry().then((mod) => {
      if (mod) {
        try {
          mod.withScope(callback as unknown as (scope: unknown) => void);
        } catch {
          // ignore
        }
      }
    });
    return;
  }
  try {
    callback({
      setExtra: () => {},
      setLevel: () => {},
    });
  } catch {
    // ignore
  }
}

export function isSentryConfigured(): boolean {
  return !!process.env.SENTRY_DSN;
}
