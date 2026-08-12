"use client";

import { useLocalParticipant, useTranscriptions } from "@livekit/components-react";

type Segment = ReturnType<typeof useTranscriptions>[number];

/**
 * Newest stream wins (by stream timestamp, not array order): interruptions
 * and discarded preemptive generations can leave stale streams interleaved,
 * which otherwise desyncs captions from what's actually being spoken.
 */
function newest(segments: Segment[]): Segment | undefined {
  return segments.reduce<Segment | undefined>(
    (best, seg) =>
      !best || (seg.streamInfo?.timestamp ?? 0) >= (best.streamInfo?.timestamp ?? 0)
        ? seg
        : best,
    undefined,
  );
}

/** Last sentence of a running transcript — what's being said right now. */
function currentSentence(text: string): string {
  const sentences = text.split(/(?<=[.!?…])\s+/).filter(Boolean);
  return sentences[sentences.length - 1] ?? "";
}

/**
 * Live comms readout: what Commander Sky is saying, one sentence at a time,
 * plus a dimmed echo of what the mic heard the visitor say. The echo makes
 * misrecognitions visible (children's STT is 2–3× less accurate) so visitors
 * can tell "she misheard me" from "she ignored me" and simply re-ask.
 * Display-only, in-memory — nothing is persisted or logged.
 * Reserved space keeps the layout stable whether or not anyone's talking.
 */
export function Captions() {
  const { localParticipant } = useLocalParticipant();
  const transcriptions = useTranscriptions();

  const agentSegments: Segment[] = [];
  const visitorSegments: Segment[] = [];
  for (const t of transcriptions) {
    (t.participantInfo.identity === localParticipant?.identity
      ? visitorSegments
      : agentSegments
    ).push(t);
  }

  const spoken = newest(agentSegments);
  const heard = newest(visitorSegments);

  const current = currentSentence(spoken?.text ?? "");

  // Show the echo only while the visitor's speech is the latest activity —
  // once Commander Sky's reply stream starts, it takes the stage back.
  const heardIsLatest =
    !!heard &&
    (heard.streamInfo?.timestamp ?? 0) >= (spoken?.streamInfo?.timestamp ?? 0);
  const heardText = heardIsLatest ? currentSentence(heard.text) : "";
  const heardIsFinal = heard?.streamInfo?.attributes?.["lk.transcription_final"] === "true";

  return (
    <div
      data-testid="captions"
      className="flex min-h-24 w-full max-w-2xl flex-col items-center justify-end gap-2 px-6"
    >
      <div className="flex min-h-6 items-center" data-testid="caption-heard">
        {heardText ? (
          <p
            className={`text-center font-mono text-sm italic text-slate-400 ${
              heardIsFinal ? "" : "opacity-70"
            }`}
          >
            <span className="mr-2 not-italic text-slate-500">You</span>
            {heardText}
          </p>
        ) : null}
      </div>
      <div aria-live="polite" className="flex min-h-16 items-center justify-center">
        {current ? (
          <p className="rounded-xl border border-cyan-400/15 bg-slate-950/70 px-5 py-2.5 text-center font-mono text-base leading-relaxed text-cyan-100/90 backdrop-blur">
            <span className="mr-2 text-cyan-500/70">»</span>
            {current}
          </p>
        ) : null}
      </div>
    </div>
  );
}
