import { AccessToken } from "livekit-server-sdk";
import { NextRequest, NextResponse } from "next/server";
import { checkRateLimit, clientIp } from "@/lib/ratelimit";

// Mints a short-lived LiveKit token for one conversation session.
// Privacy: identity and room are random UUIDs — nothing links a session to a person.
export async function POST(request: NextRequest) {
  // Optional invite gate for soft launches: set ACCESS_CODE to require it.
  const requiredCode = process.env.ACCESS_CODE;
  if (requiredCode && request.headers.get("x-access-code") !== requiredCode) {
    return NextResponse.json({ error: "access_code_required" }, { status: 401 });
  }

  const limit = await checkRateLimit(clientIp(request.headers));
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
