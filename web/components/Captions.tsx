"use client";

import { useLocalParticipant, useTranscriptions } from "@livekit/components-react";

/**
 * Live comms readout of what Commander Sky is saying — one sentence at a
 * time. Reserved space keeps the layout stable whether or not she's talking.
 */
export function Captions() {
  const { localParticipant } = useLocalParticipant();
  const transcriptions = useTranscriptions();

  const agentSegments = transcriptions.filter(
    (t) => t.participantInfo.identity !== localParticipant?.identity,
  );
  // Newest stream wins (by stream timestamp, not array order): interruptions
  // and discarded preemptive generations can leave stale streams interleaved,
  // which otherwise desyncs captions from what she's actually saying.
  const latest = agentSegments.reduce<(typeof agentSegments)[number] | undefined>(
    (best, seg) =>
      !best || (seg.streamInfo?.timestamp ?? 0) >= (best.streamInfo?.timestamp ?? 0)
        ? seg
        : best,
    undefined,
  );

  // Show only the sentence currently being spoken, not the whole reply.
  const sentences = (latest?.text ?? "").split(/(?<=[.!?…])\s+/).filter(Boolean);
  const current = sentences[sentences.length - 1] ?? "";

  return (
    <div
      aria-live="polite"
      data-testid="captions"
      className="flex min-h-16 w-full max-w-2xl items-center justify-center px-6"
    >
      {current ? (
        <p className="rounded-xl border border-cyan-400/15 bg-slate-950/70 px-5 py-2.5 text-center font-mono text-base leading-relaxed text-cyan-100/90 backdrop-blur">
          <span className="mr-2 text-cyan-500/70">»</span>
          {current}
        </p>
      ) : null}
    </div>
  );
}
