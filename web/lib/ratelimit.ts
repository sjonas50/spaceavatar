/**
 * In-memory rate limiting for session-token minting.
 *
 * Two layers of cost control:
 * - per-IP: stops one household/device from burning sessions in a loop
 * - global daily cap: bounds worst-case daily avatar spend (~$2-4.50/session)
 *
 * NOTE: state is per-server-instance. Fine for the soft launch on a single
 * region; move to a durable store (Redis/Upstash) before horizontal scaling.
 */

type Window = { count: number; resetAt: number };

const perIp = new Map<string, Window>();
let daily: Window = { count: 0, resetAt: nextMidnightUtc() };

const IP_LIMIT = Number(process.env.SESSIONS_PER_IP_PER_HOUR ?? 6);
const DAILY_LIMIT = Number(process.env.MAX_SESSIONS_PER_DAY ?? 500);
const HOUR_MS = 60 * 60 * 1000;

function nextMidnightUtc(): number {
  const now = new Date();
  return Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1);
}

export function checkRateLimit(ip: string): { allowed: boolean; reason?: string } {
  const now = Date.now();

  if (now >= daily.resetAt) daily = { count: 0, resetAt: nextMidnightUtc() };
  if (daily.count >= DAILY_LIMIT) return { allowed: false, reason: "daily_cap" };

  const window = perIp.get(ip);
  if (!window || now >= window.resetAt) {
    perIp.set(ip, { count: 1, resetAt: now + HOUR_MS });
  } else if (window.count >= IP_LIMIT) {
    return { allowed: false, reason: "ip_limit" };
  } else {
    window.count += 1;
  }

  daily.count += 1;
  if (perIp.size > 10_000) prune(now);
  return { allowed: true };
}

function prune(now: number): void {
  for (const [ip, window] of perIp) {
    if (now >= window.resetAt) perIp.delete(ip);
  }
}
