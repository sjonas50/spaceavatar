"use client";

import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant } from "@livekit/components-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AvatarView } from "@/components/AvatarView";
import { Captions } from "@/components/Captions";
import { PushToTalkButton } from "@/components/PushToTalkButton";
import { SpaceOverlay } from "@/components/SpaceOverlay";
import { TransmissionBoot } from "@/components/TransmissionBoot";
import { buildConnectOptions } from "@/lib/livekit";

// "open": mic streams continuously from page load (owner decision 2026-07-17).
// "ptt": mic only active while the talk button is engaged.
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
      <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
        <div>
          <p className="mb-4 font-mono text-xs uppercase tracking-[0.35em] text-cyan-400/80">
            Orbital Exhibit 01 · Live from low Earth orbit
          </p>
          <h1 className="font-display text-5xl font-bold text-white md:text-7xl">
            COMMANDER SKY
          </h1>
          <p className="mx-auto mt-4 max-w-md text-slate-400">
            Step up to the mic and talk with the museum&apos;s resident astronaut — live
            answers, real mission archives, and the occasional pop quiz.
          </p>
        </div>

        {needsCode ? (
          <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur">
            <p className="font-mono text-xs uppercase tracking-widest text-slate-300">
              Boarding pass required
            </p>
            <div className="flex w-full gap-2">
              <input
                data-testid="access-code"
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && start(accessCode)}
                placeholder="MISSION CODE"
                className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-4 py-3 text-center font-mono text-lg uppercase tracking-widest text-cyan-100 placeholder:text-slate-600 focus:border-cyan-400/50 focus:outline-none"
                aria-label="Mission code"
              />
              <button
                data-testid="access-code-submit"
                onClick={() => start(accessCode)}
                className="rounded-xl bg-cyan-400 px-6 py-3 font-display font-bold text-slate-950 transition hover:bg-cyan-300 active:scale-95"
              >
                Board
              </button>
            </div>
            {error && (
              <p className="text-sm text-amber-300" data-testid="session-error">
                {error}
              </p>
            )}
          </div>
        ) : ended ? (
          <div className="flex flex-col items-center gap-4">
            <p className="font-mono text-sm text-slate-400">
              Transmission ended — Commander Sky is off duty.
            </p>
            <button
              onClick={() => start(accessCode || undefined)}
              data-testid="restart-session"
              className="rounded-full bg-cyan-400 px-10 py-4 font-display text-xl font-bold text-slate-950 shadow-[0_0_40px_rgba(34,211,238,0.35)] transition hover:bg-cyan-300 active:scale-95"
            >
              Reopen the link
            </button>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-4">
            <p className="text-amber-300" data-testid="session-error">
              {error}
            </p>
            <button
              onClick={() => start(accessCode || undefined)}
              data-testid="retry-session"
              className="rounded-full bg-cyan-400 px-10 py-4 font-display text-xl font-bold text-slate-950 shadow-[0_0_40px_rgba(34,211,238,0.35)] transition hover:bg-cyan-300 active:scale-95"
            >
              Try again
            </button>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur">
            <TransmissionBoot />
          </div>
        )}

        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-600">
          No recordings · No transcripts stored · Sessions end after 15 minutes
        </p>
      </main>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={details.serverUrl}
      token={details.participantToken}
      connect
      audio={MIC_MODE === "open"} // open mode: mic publishes as soon as we join
      video={false} // we never use the visitor's camera
      connectOptions={buildConnectOptions()}
      onDisconnected={() => {
        // Session ended (sign-off, cap, idle, or network) — show the restart
        // screen instead of auto-reconnecting; nothing bills while it waits.
        startedRef.current = false;
        setEnded(true);
        setDetails(null);
      }}
      className="relative flex min-h-screen flex-col items-center justify-between py-6"
    >
      <SpaceOverlay />
      <AvatarView />
      <div className="flex flex-col items-center gap-3 pb-4">
        <Captions />
        {MIC_MODE === "open" ? <MicControl /> : <PushToTalkButton />}
      </div>
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
      className={`flex items-center gap-3 rounded-full border px-7 py-3.5 font-display text-lg transition active:scale-95 ${
        isMicrophoneEnabled
          ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
          : "border-white/10 bg-white/5 text-slate-400"
      }`}
    >
      <span
        className={`live-dot inline-block h-2.5 w-2.5 rounded-full ${
          isMicrophoneEnabled ? "bg-emerald-400" : "bg-slate-500"
        }`}
      />
      {isMicrophoneEnabled ? "Listening — tap to mute" : "Muted — tap to talk"}
    </button>
  );
}
