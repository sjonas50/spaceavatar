"use client";

import { VideoTrack, useVoiceAssistant } from "@livekit/components-react";
import { TransmissionBoot } from "@/components/TransmissionBoot";

/**
 * The exhibit viewport: avatar video in a framed "orbital link" window,
 * with the transmission boot sequence while the feed comes up.
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
        {live ? "Live — orbital link" : "Acquiring link"}
      </div>

      <div className="relative w-full max-w-3xl overflow-hidden rounded-3xl border border-cyan-400/20 bg-slate-950/60 shadow-[0_0_80px_rgba(34,211,238,0.12)] backdrop-blur">
        {videoTrack ? (
          <VideoTrack trackRef={videoTrack} className="max-h-[62vh] w-full object-contain" />
        ) : (
          <div className="flex min-h-[40vh] flex-col items-center justify-center gap-6 p-8">
            <div className="animate-[float_3s_ease-in-out_infinite] text-7xl">🧑‍🚀</div>
            <TransmissionBoot />
          </div>
        )}
      </div>
    </div>
  );
}
