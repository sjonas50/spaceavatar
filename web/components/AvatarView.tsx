"use client";

import { VideoTrack, useVoiceAssistant } from "@livekit/components-react";
import { ThinkingCue } from "@/components/ThinkingCue";

/**
 * Fullscreen avatar area.
 *
 * - lemonslice mode: renders the avatar's synced video track.
 * - frontend/none mode (no video track): renders the locally-animated
 *   character — floats when idle, glows while speaking. Never a spinner.
 */
export function AvatarView() {
  const { state, videoTrack } = useVoiceAssistant();

  return (
    <div className="relative flex w-full flex-1 flex-col items-center justify-center">
      {videoTrack ? (
        <VideoTrack
          trackRef={videoTrack}
          className="max-h-[70vh] w-auto rounded-3xl object-contain"
        />
      ) : (
        <FrontendCharacter speaking={state === "speaking"} connected={state !== "connecting"} />
      )}
      <div className="absolute bottom-4 h-12">
        {state === "thinking" && <ThinkingCue />}
      </div>
    </div>
  );
}

/** Placeholder Commander Sky for frontend mode until the designed character lands. */
function FrontendCharacter({
  speaking,
  connected,
}: {
  speaking: boolean;
  connected: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-6" data-testid="frontend-character">
      <div
        className={`text-[10rem] leading-none transition-transform duration-500 ${
          speaking
            ? "scale-110 drop-shadow-[0_0_40px_rgba(52,211,153,0.8)]"
            : "animate-[float_3s_ease-in-out_infinite]"
        }`}
      >
        🧑‍🚀
      </div>
      {!connected && (
        <p className="animate-pulse text-xl text-slate-300">
          Commander Sky is floating over…
        </p>
      )}
    </div>
  );
}
