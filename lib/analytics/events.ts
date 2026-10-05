import { trackEvent } from "./posthog";

// ── Typed event definitions ─────────────────────────────────────────────

export type AnalyticsEvent =
  | { name: "cta_click"; props: { location: string; label: string; href: string } }
  | { name: "preflop_chart_view"; props: { position: string; stack: string; source?: string } }
  | { name: "preflop_hand_hover"; props: { hand: string; position: string; stack: string } }
  | { name: "hand_parse"; props: { count: number; site?: string; success: boolean } }
  | { name: "drill_started"; props: { leakId: string; leakLabel?: string } }
  | { name: "drill_completed"; props: { drillId: string; leakId: string; score: number; correct: number; total: number } }
  | { name: "drill_answer"; props: { drillId: string; handId: string; correct: boolean; chosenAction: string } }
  | { name: "checkout_click"; props: { plan: string; location: string } }
  | { name: "checkout_success"; props: { plan: string; sessionId?: string } }
  | { name: "blog_post_view"; props: { slug: string; category: string; title: string } }
  | { name: "email_subscribe"; props: { source: string; variant: string; success: boolean } }
  | { name: "email_confirm"; props: { success: boolean } }
  | { name: "coach_request"; props: { spotHash?: string; tone?: string } }
  | { name: "solver_request"; props: { street: string; source: string } };

export type EventName = AnalyticsEvent["name"];
export type EventProps<T extends EventName> = Extract<AnalyticsEvent, { name: T }>["props"];

// ── Helper: typed track ─────────────────────────────────────────────────

export function track<T extends EventName>(name: T, props: EventProps<T>): void {
  trackEvent(name, props as Record<string, unknown>);
}

// ── Convenience wrappers for key conversion events ──────────────────────

export const analytics = {
  ctaClick: (location: string, label: string, href: string) =>
    track("cta_click", { location, label, href }),

  preflopChartView: (position: string, stack: string, source?: string) =>
    track("preflop_chart_view", { position, stack, source }),

  preflopHandHover: (hand: string, position: string, stack: string) =>
    track("preflop_hand_hover", { hand, position, stack }),

  handParse: (count: number, success: boolean, site?: string) =>
    track("hand_parse", { count, success, site }),

  drillStarted: (leakId: string, leakLabel?: string) =>
    track("drill_started", { leakId, leakLabel }),

  drillCompleted: (drillId: string, leakId: string, score: number, correct: number, total: number) =>
    track("drill_completed", { drillId, leakId, score, correct, total }),

  drillAnswer: (drillId: string, handId: string, correct: boolean, chosenAction: string) =>
    track("drill_answer", { drillId, handId, correct, chosenAction }),

  checkoutClick: (plan: string, location: string) =>
    track("checkout_click", { plan, location }),

  checkoutSuccess: (plan: string, sessionId?: string) =>
    track("checkout_success", { plan, sessionId }),

  blogPostView: (slug: string, category: string, title: string) =>
    track("blog_post_view", { slug, category, title }),

  emailSubscribe: (source: string, variant: string, success: boolean) =>
    track("email_subscribe", { source, variant, success }),

  emailConfirm: (success: boolean) =>
    track("email_confirm", { success }),

  coachRequest: (spotHash?: string, tone?: string) =>
    track("coach_request", { spotHash, tone }),

  solverRequest: (street: string, source: string) =>
    track("solver_request", { street, source }),
};
