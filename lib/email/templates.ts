const SITE_URL = process.env.NEXT_PUBLIC_APP_URL || "https://aipokerlab.com";
const FROM_NAME = "AI Poker Lab";

function wrapHtml(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title></head>
<body style="margin:0;padding:0;background:#fafafa;font-family:Inter,system-ui,-apple-system,sans-serif;color:#18181b;">
  <div style="max-width:560px;margin:0 auto;padding:24px;">
    <div style="text-align:center;padding:16px 0;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:10px;background:#059669;color:#fff;font-weight:800;font-size:18px;">♠</span>
      <span style="margin-left:8px;font-weight:800;font-size:18px;letter-spacing:-0.02em;">AI Poker Lab</span>
    </div>
    ${body}
    <div style="margin-top:24px;padding:16px;border-top:1px solid #e4e4e7;text-align:center;font-size:12px;color:#71717a;line-height:1.6;">
      <p style="margin:0;">Training tool only — not for use during play. Compliant with PokerStars / GGPoker ToS.</p>
      <p style="margin:8px 0 0;"><a href="${SITE_URL}" style="color:#059669;font-weight:600;">aipokerlab.com</a> · <a href="${SITE_URL}/privacy" style="color:#71717a;">Privacy</a> · <a href="${SITE_URL}/terms" style="color:#71717a;">Terms</a></p>
      <p style="margin:8px 0 0;">You received this because you subscribed at ${SITE_URL}. <a href="{{unsubscribe_url}}" style="color:#71717a;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>`;
}

export function welcomeEmailHtml(opts: { email: string; confirmUrl?: string }): string {
  const ctaUrl = opts.confirmUrl || `${SITE_URL}/lab/preflop`;
  const body = `
    <div style="background:#fff;border:1px solid #e4e4e7;border-radius:16px;padding:28px;">
      <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:-0.02em;">Welcome to AI Poker Lab ♠</h1>
      <p style="margin:12px 0 0;font-size:14px;line-height:1.7;color:#3f3f46;">You're in. Here's your free gift to get started:</p>
      <div style="margin:16px 0;padding:16px;border:1px solid #a7f3d0;background:#ecfdf5;border-radius:12px;">
        <p style="margin:0;font-weight:700;font-size:14px;color:#065f46;">Free Preflop Charts — 6 positions × 4 stacks</p>
        <p style="margin:6px 0 0;font-size:13px;line-height:1.6;color:#065f46;">Interactive 13×13 range grids with GTO raise/call/fold frequencies and EV, backed by our O(1) spotHash DB and Rust Linear MCCFR solver.</p>
        <a href="${SITE_URL}/lab/preflop" style="display:inline-block;margin-top:12px;background:#059669;color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:10px 18px;border-radius:999px;">Open Preflop Lab →</a>
      </div>
      ${opts.confirmUrl ? `<p style="margin:16px 0 0;font-size:13px;line-height:1.6;color:#3f3f46;">Please confirm your email to activate your subscription:</p><a href="${ctaUrl}" style="display:inline-block;margin-top:8px;background:#18181b;color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:10px 18px;border-radius:999px;">Confirm Email →</a><p style="margin:8px 0 0;font-size:12px;color:#71717a;">Or paste: ${ctaUrl}</p>` : ``}
      <p style="margin:16px 0 0;font-size:13px;line-height:1.6;color:#3f3f46;">Next steps: paste a hand in the <a href="${SITE_URL}/replayer" style="color:#059669;font-weight:600;">Replayer</a>, see your leaks, and let the AI Coach explain every mistake.</p>
    </div>`;
  return wrapHtml(`Welcome to ${FROM_NAME}`, body);
}

export function welcomeEmailText(opts: { email: string; confirmUrl?: string }): string {
  return `Welcome to AI Poker Lab!

Your free Preflop Charts: ${SITE_URL}/lab/preflop (6 positions × 4 stacks, GTO frequencies + EV)

${opts.confirmUrl ? `Confirm your email: ${opts.confirmUrl}\n\n` : ""}Next: paste a hand in the Replayer (${SITE_URL}/replayer) and see your leaks.

— AI Poker Lab (training only, not for use during play)
${SITE_URL}`;
}

export function drillReminderHtml(opts: { email: string; leak: string; leakLabel?: string }): string {
  const leakLabel = opts.leakLabel || opts.leak;
  const body = `
    <div style="background:#fff;border:1px solid #e4e4e7;border-radius:16px;padding:28px;">
      <h1 style="margin:0;font-size:20px;font-weight:800;">Your leak needs attention 🎯</h1>
      <p style="margin:12px 0 0;font-size:14px;line-height:1.7;color:#3f3f46;">Your biggest leak right now is <strong>${escapeHtml(leakLabel)}</strong> (<code>${escapeHtml(opts.leak)}</code>). Let's fix it with a quick drill.</p>
      <div style="margin:16px 0;padding:16px;border:1px solid #fde68a;background:#fffbeb;border-radius:12px;">
        <p style="margin:0;font-weight:700;font-size:14px;color:#92400e;">5-minute drill — spaced repetition</p>
        <p style="margin:6px 0 0;font-size:13px;line-height:1.6;color:#92400e;">We generated hands targeting this leak. Answer raise/call/fold and get instant GTO feedback.</p>
        <a href="${SITE_URL}/drills?leak=${encodeURIComponent(opts.leak)}" style="display:inline-block;margin-top:12px;background:#d97706;color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:10px 18px;border-radius:999px;">Start Drill →</a>
      </div>
      <p style="margin:16px 0 0;font-size:12px;color:#71717a;">You're receiving this because you subscribed to drill reminders. Unsubscribe anytime.</p>
    </div>`;
  return wrapHtml(`Fix your leak: ${leakLabel}`, body);
}

export function drillReminderText(opts: { email: string; leak: string; leakLabel?: string }): string {
  return `Your leak: ${opts.leakLabel || opts.leak} (${opts.leak})

Fix it with a 5-min drill: ${SITE_URL}/drills?leak=${encodeURIComponent(opts.leak)}

— AI Poker Lab`;
}

export function weeklyProgressHtml(opts: { email: string; stats: { handsReviewed: number; leaksFixed?: number; xp?: number; topLeak?: string } }): string {
  const s = opts.stats;
  const body = `
    <div style="background:#fff;border:1px solid #e4e4e7;border-radius:16px;padding:28px;">
      <h1 style="margin:0;font-size:20px;font-weight:800;">Your weekly progress 📈</h1>
      <p style="margin:12px 0 0;font-size:14px;line-height:1.7;color:#3f3f46;">Here's how you did this week:</p>
      <div style="margin:16px 0;display:grid;gap:8px;">
        <div style="padding:12px;border:1px solid #e4e4e7;border-radius:10px;background:#fafafa;"><strong>${s.handsReviewed}</strong> hands reviewed</div>
        ${s.leaksFixed !== undefined ? `<div style="padding:12px;border:1px solid #e4e4e7;border-radius:10px;background:#fafafa;"><strong>${s.leaksFixed}</strong> leaks improved</div>` : ""}
        ${s.xp !== undefined ? `<div style="padding:12px;border:1px solid #e4e4e7;border-radius:10px;background:#fafafa;"><strong>${s.xp}</strong> XP earned</div>` : ""}
        ${s.topLeak ? `<div style="padding:12px;border:1px solid #fde68a;border-radius:10px;background:#fffbeb;">Top leak to fix: <strong>${escapeHtml(s.topLeak)}</strong></div>` : ""}
      </div>
      <a href="${SITE_URL}/dashboard" style="display:inline-block;margin-top:8px;background:#059669;color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:10px 18px;border-radius:999px;">Open Dashboard →</a>
    </div>`;
  return wrapHtml(`Your weekly progress`, body);
}

export function weeklyProgressText(opts: { email: string; stats: { handsReviewed: number; leaksFixed?: number; xp?: number; topLeak?: string } }): string {
  const s = opts.stats;
  return `Weekly progress:
- Hands reviewed: ${s.handsReviewed}
${s.leaksFixed !== undefined ? `- Leaks improved: ${s.leaksFixed}\n` : ""}${s.xp !== undefined ? `- XP: ${s.xp}\n` : ""}${s.topLeak ? `- Top leak: ${s.topLeak}\n` : ""}
Open dashboard: ${SITE_URL}/dashboard

— AI Poker Lab`;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
