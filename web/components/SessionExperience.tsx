"use client";

import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant } from "@livekit/components-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AvatarView } from "@/components/AvatarView";
import { Captions } from "@/components/Captions";
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
  const [needsCode, setNeedsCode] = useState(false);
  const [accessCode, setAccessCode] = useState("");
  const [ended, setEnded] = useState(false);
  const startedRef = useRef(false);

  const start = useCallback(async (code?: string) => {
    setError(null);
    try {
      const res = await fetch("/api/token", {
        method: "POST",
        headers: code ? { "x-access-code": code } : {},
      });
      if (res.status === 401) {
        setNeedsCode(true);
        if (code) setError("That's not the right mission code — try again.");
        return;
      }
      if (!res.ok) throw new Error(`token request failed: ${res.status}`);
      setNeedsCode(false);
      setEnded(false);
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
        {needsCode ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-slate-300">Enter your mission code to board.</p>
            <div className="flex gap-2">
              <input
                data-testid="access-code"
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && start(accessCode)}
                className="rounded-xl bg-slate-800 px-4 py-3 text-center text-xl"
                aria-label="Mission code"
              />
              <button
                data-testid="access-code-submit"
                onClick={() => start(accessCode)}
                className="rounded-xl bg-emerald-500 px-6 py-3 font-bold"
              >
                Board
              </button>
            </div>
            {error && (
              <p className="text-amber-300" data-testid="session-error">
                {error}
              </p>
            )}
          </div>
        ) : ended ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-slate-300">Mission complete — Commander Sky is off duty.</p>
            <button
              onClick={() => start(accessCode || undefined)}
              data-testid="restart-session"
              className="rounded-full bg-emerald-500 px-10 py-5 text-2xl font-bold shadow-xl transition-transform active:scale-95"
            >
              Talk to her again
            </button>
          </div>
        ) : error ? (
          <>
            <p className="text-amber-300" data-testid="session-error">
              {error}
            </p>
            <button
              onClick={() => start(accessCode || undefined)}
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
        // Session ended (sign-off, cap, idle, or network) — show the restart
        // screen instead of auto-reconnecting; nothing bills while it waits.
        startedRef.current = false;
        setEnded(true);
        setDetails(null);
      }}
      className="relative flex min-h-screen flex-col items-center justify-between bg-slate-950 py-8 text-white"
    >
      <SpaceOverlay />
      <AvatarView />
      <Captions />
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
