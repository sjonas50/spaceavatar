"use client";

import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant } from "@livekit/components-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AvatarView } from "@/components/AvatarView";
import { PushToTalkButton } from "@/components/PushToTalkButton";
import { SpaceOverlay } from "@/components/SpaceOverlay";
import { buildConnectOptions } from "@/lib/livekit";

// "open": mic streams continuously from page load (owner decision 2026-07-17).
// "ptt": mic only active while the talk button is engaged — the COPPA-preferred
// posture; restore with NEXT_PUBLIC_MIC_MODE=ptt before public launch review.
const MIC_MODE = process.env.NEXT_PUBLIC_MIC_MODE === "ptt" ? "ptt" : "open";

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantToken: string;
};

export function SessionExperience() {
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  const start = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch("/api/token", { method: "POST" });
      if (!res.ok) throw new Error(`token request failed: ${res.status}`);
      setDetails(await res.json());
    } catch {
      setError("Couldn't reach mission control. Try again in a moment!");
    }
  }, []);

  // Auto-connect on load. The ref guards React StrictMode's double-mount from
  // minting two rooms (each orphan room would start a billable avatar session).
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    start();
  }, [start]);

  if (!details) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-950 text-white">
        <div className="animate-[float_3s_ease-in-out_infinite] text-8xl">🧑‍🚀</div>
        <h1 className="text-4xl font-bold">Commander Sky</h1>
        {error ? (
          <>
            <p className="text-amber-300" data-testid="session-error">
              {error}
            </p>
            <button
              onClick={start}
              data-testid="retry-session"
              className="rounded-full bg-emerald-500 px-10 py-5 text-2xl font-bold shadow-xl transition-transform active:scale-95"
            >
              Try again
            </button>
          </>
        ) : (
          <p className="animate-pulse text-xl text-slate-300">Calling the station…</p>
        )}
      </main>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={details.serverUrl}
      token={details.participantToken}
      connect
      audio={MIC_MODE === "open"} // open mode: mic publishes as soon as we join
      video={false} // we never use the child's camera
      connectOptions={buildConnectOptions()}
      onDisconnected={() => {
        startedRef.current = false;
        setDetails(null);
      }}
      className="relative flex min-h-screen flex-col items-center justify-between bg-slate-950 py-8 text-white"
    >
      <SpaceOverlay />
      <AvatarView />
      <div className="pb-4">{MIC_MODE === "open" ? <MicControl /> : <PushToTalkButton />}</div>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

/** Open-mic mode: always listening, with a mute toggle as the escape hatch. */
function MicControl() {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  return (
    <button
      onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
      aria-pressed={!isMicrophoneEnabled}
      aria-label={isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}
      className={`rounded-full px-8 py-4 text-xl font-bold shadow-xl transition-transform active:scale-95 ${
        isMicrophoneEnabled ? "bg-emerald-500" : "bg-slate-600"
      }`}
    >
      {isMicrophoneEnabled ? "👂 I'm listening — tap to mute" : "🔇 Muted — tap to talk"}
    </button>
  );
}
