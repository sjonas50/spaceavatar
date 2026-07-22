"use client";

import { VideoTrack, useVoiceAssistant } from "@livekit/components-react";
import { TransmissionBoot } from "@/components/TransmissionBoot";

/**
 * The exhibit viewport: avatar video in a framed "orbital link" window.
 * Boot sequence while the feed spins up; audio-only presentation if the
 * agent is live but no video track ever arrives (avatar fallback mode).
 */
export function AvatarView() {
  const { state, videoTrack } = useVoiceAssistant();
  const live = state === "listening" || state === "speaking" || state === "thinking";

  return (
    <div className="flex w-full flex-1 flex-col items-center justify-center gap-4 px-4">
      <div className="flex items-center gap-2 self-center rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-mono uppercase tracking-widest text-slate-300 backdrop-blur">
        <span
          className={`live-dot inline-block h-2 w-2 rounded-full ${live ? "bg-emerald-400" : "bg-amber-400"}`}
        />
        {videoTrack ? "Live — orbital link" : live ? "Live — audio-only link" : "Acquiring link"}
      </div>

      <div className="relative w-full max-w-3xl overflow-hidden rounded-3xl border border-cyan-400/20 bg-slate-950/60 shadow-[0_0_80px_rgba(34,211,238,0.12)] backdrop-blur">
        {videoTrack ? (
          // Keyed on the track so the reveal animation replays on (re)connect
          <div key={videoTrack.publication?.trackSid ?? "video"} className="signal-acquired">
            <VideoTrack trackRef={videoTrack} className="max-h-[62vh] w-full object-contain" />
          </div>
        ) : (
          <div className="flex min-h-[40vh] flex-col items-center justify-center gap-6 p-8">
            <div
              className={`text-7xl ${
                state === "speaking"
                  ? "scale-110 drop-shadow-[0_0_40px_rgba(52,211,153,0.7)] transition-transform"
                  : "animate-[float_3s_ease-in-out_infinite]"
              }`}
            >
              🧑‍🚀
            </div>
            {live ? (
              <p className="font-mono text-xs uppercase tracking-widest text-cyan-400/70">
                Video feed offline — voice link active
              </p>
            ) : (
              <TransmissionBoot />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
