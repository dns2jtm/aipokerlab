import { welcomeEmailHtml, welcomeEmailText, drillReminderHtml, drillReminderText, weeklyProgressHtml, weeklyProgressText } from "./templates";

const FROM_EMAIL = process.env.RESEND_FROM_EMAIL || "AI Poker Lab <hello@aipokerlab.com>";
const API_KEY = process.env.RESEND_API_KEY;

type SendResult = { id?: string; mock: boolean; error?: string };

async function sendEmail(opts: { to: string; subject: string; html: string; text?: string }): Promise<SendResult> {
  if (!API_KEY) {
    console.log(`[Resend mock] To: ${opts.to} | Subject: ${opts.subject}\n${opts.text || opts.html.slice(0, 500)}`);
    return { mock: true, id: `mock_${Date.now()}` };
  }
  try {
    const { Resend } = await import("resend");
    const resend = new Resend(API_KEY);
    const result = await resend.emails.send({
      from: FROM_EMAIL,
      to: opts.to,
      subject: opts.subject,
      html: opts.html,
      text: opts.text,
    });
    if (result.error) {
      console.error("[Resend] send error", result.error);
      return { mock: false, error: String(result.error) };
    }
    return { mock: false, id: result.data?.id };
  } catch (err) {
    console.error("[Resend] exception", err);
    return { mock: false, error: String(err) };
  }
}

export async function sendWelcomeEmail(email: string, confirmUrl?: string): Promise<SendResult> {
  return sendEmail({
    to: email,
    subject: "Welcome to AI Poker Lab — your free preflop charts inside ♠",
    html: welcomeEmailHtml({ email, confirmUrl }),
    text: welcomeEmailText({ email, confirmUrl }),
  });
}

export async function sendDrillReminder(email: string, leak: string, leakLabel?: string): Promise<SendResult> {
  return sendEmail({
    to: email,
    subject: `Fix your leak: ${leakLabel || leak} — 5-min drill inside`,
    html: drillReminderHtml({ email, leak, leakLabel }),
    text: drillReminderText({ email, leak, leakLabel }),
  });
}

export async function sendWeeklyProgress(
  email: string,
  stats: { handsReviewed: number; leaksFixed?: number; xp?: number; topLeak?: string }
): Promise<SendResult> {
  return sendEmail({
    to: email,
    subject: `Your weekly progress — ${stats.handsReviewed} hands reviewed`,
    html: weeklyProgressHtml({ email, stats }),
    text: weeklyProgressText({ email, stats }),
  });
}

export function isResendConfigured(): boolean {
  return !!API_KEY;
}
