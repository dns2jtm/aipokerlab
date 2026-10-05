/**
 * HTML sanitization and input sanitization utilities.
 * No external deps — lightweight allowlist approach.
 */

const ALLOWED_TAGS = new Set(["p", "br", "strong", "em", "ul", "ol", "li", "a", "h2", "h3", "h4", "code", "pre", "blockquote"]);
const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(["href", "rel", "target"]),
};

/**
 * Strip all HTML tags except allowlisted ones, and sanitize attributes.
 * For blog content rendering.
 */
export function sanitizeHtml(dirty: string): string {
  if (!dirty || typeof dirty !== "string") return "";
  // Remove script/style/iframe/object/embed tags entirely with content
  let clean = dirty.replace(/<(script|style|iframe|object|embed|form|input|button|select|textarea|link|meta)[^>]*>[\s\S]*?<\/\1\s*>/gi, "");
  clean = clean.replace(/<(script|style|iframe|object|embed|form|input|button|select|textarea|link|meta)[^>]*\/?>/gi, "");
  // Remove event handlers and javascript: urls
  clean = clean.replace(/\s*on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]*)/gi, "");
  clean = clean.replace(/href\s*=\s*["']?\s*javascript:[^"'>\s]*/gi, 'href="#"');
  // Strip disallowed tags but keep content
  clean = clean.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g, (match, tag: string) => {
    const lower = tag.toLowerCase();
    if (!ALLOWED_TAGS.has(lower)) return "";
    // For allowed tags, strip disallowed attributes
    if (lower === "a") {
      const hrefMatch = match.match(/href\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/i);
      let href = "";
      if (hrefMatch) {
        const raw = hrefMatch[1].replace(/^["']|["']$/g, "");
        if (/^https?:\/\//i.test(raw) || raw.startsWith("/") || raw.startsWith("#")) {
          href = ` href="${raw.replace(/"/g, "&quot;")}"`;
        }
      }
      const isClosing = match.startsWith("</");
      if (isClosing) return `</a>`;
      // Always add rel for external
      const rel = href.includes("http") ? ' rel="noopener noreferrer"' : "";
      return `<a${href}${rel}>`;
    }
    // For other allowed tags, strip all attributes
    if (match.startsWith("</")) return `</${lower}>`;
    if (lower === "br") return "<br />";
    return `<${lower}>`;
  });
  return clean;
}

/**
 * Escape HTML entities for safe text insertion.
 */
export function escapeHtml(text: string): string {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/**
 * Sanitize hand history input: limit size, strip dangerous characters, prevent ReDoS.
 */
export const HAND_HISTORY_MAX_BYTES = 100 * 1024; // 100KB

export function sanitizeHandHistoryInput(raw: string): { sanitized: string; error?: string } {
  if (typeof raw !== "string") return { sanitized: "", error: "Input must be a string" };
  if (raw.length > HAND_HISTORY_MAX_BYTES) {
    return { sanitized: raw.slice(0, HAND_HISTORY_MAX_BYTES), error: `Input too large (max ${HAND_HISTORY_MAX_BYTES / 1024}KB)` };
  }
  // Strip null bytes and control chars except newline/tab
  let s = raw.replace(/\x00/g, "");
  s = s.replace(/[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
  // Limit lines to prevent ReDoS via huge single line
  const lines = s.split("\n");
  if (lines.length > 5000) {
    return { sanitized: lines.slice(0, 5000).join("\n"), error: "Too many lines (max 5000)" };
  }
  // Truncate overly long lines (prevent catastrophic backtracking)
  const truncated = lines.map((l) => (l.length > 2000 ? l.slice(0, 2000) : l)).join("\n");
  return { sanitized: truncated };
}

/**
 * Validate and sanitize email strictly.
 */
export function sanitizeEmail(email: string): { valid: boolean; sanitized: string; error?: string } {
  if (typeof email !== "string") return { valid: false, sanitized: "", error: "Email must be a string" };
  const s = email.trim().toLowerCase().slice(0, 254);
  // Strict RFC-ish regex without ReDoS risk
  const re = /^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/i;
  if (!re.test(s)) return { valid: false, sanitized: s, error: "Invalid email format" };
  if (s.includes("..")) return { valid: false, sanitized: s, error: "Invalid email format" };
  const parts = s.split("@");
  if (parts[0].length > 64) return { valid: false, sanitized: s, error: "Local part too long" };
  if (parts[1].length > 253) return { valid: false, sanitized: s, error: "Domain too long" };
  return { valid: true, sanitized: s };
}
