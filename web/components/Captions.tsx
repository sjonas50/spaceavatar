"use client";

import { useLocalParticipant, useTranscriptions } from "@livekit/components-react";

/**
 * Live caption of what Commander Sky is saying, streamed from the agent's
 * transcription text stream. Reserved space keeps the layout stable whether
 * or not she's talking.
 */
export function Captions() {
  const { localParticipant } = useLocalParticipant();
  const transcriptions = useTranscriptions();

  const agentSegments = transcriptions.filter(
    (t) => t.participantInfo.identity !== localParticipant?.identity,
  );
  const latest = agentSegments[agentSegments.length - 1];

  // Show only the sentence currently being spoken, not the whole reply.
  const sentences = (latest?.text ?? "").split(/(?<=[.!?…])\s+/).filter(Boolean);
  const current = sentences[sentences.length - 1] ?? "";

  return (
    <div
      aria-live="polite"
      data-testid="captions"
      className="flex min-h-20 w-full max-w-2xl items-center justify-center px-6"
    >
      {current ? (
        <p className="rounded-2xl bg-slate-900/80 px-5 py-3 text-center text-lg leading-relaxed text-slate-100 shadow-lg">
          {current}
        </p>
      ) : null}
    </div>
  );
}
