import { AccessToken } from "livekit-server-sdk";
import { NextRequest, NextResponse } from "next/server";
import { checkRateLimit } from "@/lib/ratelimit";

// Mints a short-lived LiveKit token for one conversation session.
// COPPA: identity and room are random UUIDs — nothing links a session to a child.
export async function POST(request: NextRequest) {
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const limit = checkRateLimit(ip);
  if (!limit.allowed) {
    // 429 with no detail — the client shows its own friendly message.
    return NextResponse.json({ error: "try again later" }, { status: 429 });
  }

  const serverUrl = process.env.LIVEKIT_URL;
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  if (!serverUrl || !apiKey || !apiSecret) {
    return NextResponse.json({ error: "server not configured" }, { status: 500 });
  }

  const maxMinutes = Number(process.env.MAX_SESSION_MINUTES ?? 15);
  const room = `sky-${crypto.randomUUID()}`;
  const identity = `explorer-${crypto.randomUUID()}`;

  const token = new AccessToken(apiKey, apiSecret, {
    identity,
    // Token outlives the session cap slightly so the agent's sign-off isn't cut off.
    ttl: `${maxMinutes + 2}m`,
  });
  token.addGrant({
    room,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  });

  return NextResponse.json({
    serverUrl,
    roomName: room,
    participantToken: await token.toJwt(),
  });
}
