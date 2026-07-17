import type { RoomConnectOptions } from "livekit-client";

/**
 * Connect options tuned for our audience's networks.
 *
 * Kids are disproportionately on iPads behind school/home networks that block
 * UDP (~15-20% of connections fail without relay), so we force TURN relay by
 * default — LiveKit Cloud relays over TLS/443. Set NEXT_PUBLIC_ICE_POLICY=all
 * to allow direct connections (e.g. local development).
 */
export function buildConnectOptions(): RoomConnectOptions {
  const policy =
    process.env.NEXT_PUBLIC_ICE_POLICY === "all" ? "all" : ("relay" as const);
  return {
    rtcConfig: { iceTransportPolicy: policy },
    maxRetries: 3,
  };
}
