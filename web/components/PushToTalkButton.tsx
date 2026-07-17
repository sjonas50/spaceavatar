"use client";

import { useLocalParticipant } from "@livekit/components-react";
import { useCallback, useState } from "react";

/**
 * Giant tap-to-talk / tap-to-stop button.
 * COPPA + predictability: the microphone is ONLY active while this is engaged —
 * there is no open-mic mode anywhere in the app.
 */
export function PushToTalkButton() {
  const { localParticipant } = useLocalParticipant();
  const [talking, setTalking] = useState(false);
  const [busy, setBusy] = useState(false);

  const toggle = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const next = !talking;
      await localParticipant.setMicrophoneEnabled(next);
      setTalking(next);
    } finally {
      setBusy(false);
    }
  }, [busy, talking, localParticipant]);

  return (
    <button
      onClick={toggle}
      aria-pressed={talking}
      aria-label={talking ? "Stop talking" : "Start talking"}
      className={`h-32 w-32 rounded-full text-5xl shadow-xl transition-transform active:scale-95 sm:h-40 sm:w-40 ${
        talking
          ? "animate-pulse bg-red-500 ring-8 ring-red-300"
          : "bg-emerald-500 ring-8 ring-emerald-300"
      }`}
    >
      {talking ? "🔴" : "🎙️"}
    </button>
  );
}
