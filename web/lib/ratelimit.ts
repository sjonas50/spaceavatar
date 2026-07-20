/**
 * Rate limiting for session-token minting — the cost-control chokepoint
 * (every approved token can burn real avatar/LLM dollars).
 *
 * Durable path: Upstash Redis via REST (set UPSTASH_REDIS_REST_URL and
 * UPSTASH_REDIS_REST_TOKEN) — correct across serverless instances and
 * deploys. Fixed windows: per-IP per hour, global per UTC day.
 *
 * Fallback: in-memory windows, per-instance only. Fine for local dev;
 * NOT sufficient for a public deployment on serverless.
 */

type Result = { allowed: boolean; reason?: string };

const IP_LIMIT = Number(process.env.SESSIONS_PER_IP_PER_HOUR ?? 6);
const DAILY_LIMIT = Number(process.env.MAX_SESSIONS_PER_DAY ?? 50);
const HOUR_MS = 60 * 60 * 1000;

export async function checkRateLimit(ip: string): Promise<Result> {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (url && token) {
    try {
      return await checkUpstash(url, token, ip);
    } catch (err) {
      console.warn("upstash rate limit unavailable, using in-memory fallback", err);
      return checkMemory(ip);
    }
  }
  return checkMemory(ip);
}

/** The client IP as attested by the platform — never the spoofable first XFF entry. */
export function clientIp(headers: Headers): string {
  return (
    headers.get("x-real-ip") ?? // set by Vercel/most platforms from the connection
    headers.get("x-forwarded-for")?.split(",").pop()?.trim() ?? // last hop, appended by our proxy
    "unknown"
  );
}

// --- Upstash (durable) ------------------------------------------------------

async function checkUpstash(url: string, token: string, ip: string): Promise<Result> {
  const hourBucket = Math.floor(Date.now() / HOUR_MS);
  const day = new Date().toISOString().slice(0, 10);
  const ipKey = `rl:ip:${ip}:${hourBucket}`;
  const dayKey = `rl:day:${day}`;

  const res = await fetch(`${url}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify([
      ["INCR", ipKey],
      ["EXPIRE", ipKey, "4000", "NX"],
      ["INCR", dayKey],
      ["EXPIRE", dayKey, "90000", "NX"],
    ]),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`upstash ${res.status}`);
  const rows = (await res.json()) as { result: number }[];
  const ipCount = rows[0]?.result ?? 0;
  const dayCount = rows[2]?.result ?? 0;

  if (dayCount > DAILY_LIMIT) return { allowed: false, reason: "daily_cap" };
  if (ipCount > IP_LIMIT) return { allowed: false, reason: "ip_limit" };
  return { allowed: true };
}

// --- In-memory (dev fallback) ----------------------------------------------

type Window = { count: number; resetAt: number };

const perIp = new Map<string, Window>();
let daily: Window = { count: 0, resetAt: nextMidnightUtc() };

function nextMidnightUtc(): number {
  const now = new Date();
  return Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1);
}

function checkMemory(ip: string): Result {
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
