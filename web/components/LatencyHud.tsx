"use client";

import { useLocalParticipant } from "@livekit/components-react";
import { useEffect, useRef, useState } from "react";

const ON_RMS = 0.01;
const POLL_MS = 25;
const HANGOVER_MS = 700;

/**
 * RMS energy tap: fires onSpeechStart at the first loud frame and
 * onSpeechEnd(t) after speech stops, stamped with when the energy actually
 * dropped (the hangover only debounces intra-sentence pauses).
 * Returns a cleanup function.
 */
function tapStream(
  ctx: AudioContext,
  stream: MediaStream,
  handlers: { onSpeechStart?: () => void; onSpeechEnd?: (t: number) => void },
): () => void {
  if (!stream.getAudioTracks().length) return () => {};
  const src = ctx.createMediaStreamSource(stream);
  const an = ctx.createAnalyser();
  an.fftSize = 2048;
  src.connect(an);
  const buf = new Float32Array(an.fftSize);
  let speaking = false;
  let lastAbove = 0;
  const timer = setInterval(() => {
    an.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const rms = Math.sqrt(sum / buf.length);
    const now = performance.now();
    if (rms > ON_RMS) {
      if (!speaking) {
        speaking = true;
        handlers.onSpeechStart?.();
      }
      lastAbove = now;
    } else if (speaking && now - lastAbove > HANGOVER_MS) {
      speaking = false;
      handlers.onSpeechEnd?.(lastAbove);
    }
  }, POLL_MS);
  return () => {
    clearInterval(timer);
    src.disconnect();
  };
}

/**
 * On-device perceived-latency HUD, enabled with `?lat=1`. Mirrors probe v2
 * (web/e2e/latency-probe.mjs): RMS energy taps on the visitor's mic and on
 * every remote track, pairing end-of-question with response onset. Exists to
 * validate the delivery-path latency on real hardware (iPad Safari) where the
 * probe script can't run. Shows numbers only — no speech content, nothing
 * persisted or transmitted (COPPA posture unchanged).
 */
export function LatencyHud() {
  const { microphoneTrack } = useLocalParticipant();
  const [gaps, setGaps] = useState<number[]>([]);
  const ctxRef = useRef<AudioContext | null>(null);
  const lastMicOffRef = useRef<number | null>(null);

  useEffect(() => {
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    // iOS starts AudioContexts suspended until a user gesture.
    const resume = () => void ctx.resume();
    document.addEventListener("pointerdown", resume);
    resume();

    // Remote side: tap every media element the app attaches a stream to. A
    // response onset consumes the pending end-of-question mark, if any (the
    // greeting has none and is skipped).
    const cleanups: (() => void)[] = [];
    const tapped = new WeakSet<MediaStream>();
    const domPoll = setInterval(() => {
      for (const el of document.querySelectorAll<HTMLMediaElement>("audio, video")) {
        const stream = el.srcObject;
        if (stream instanceof MediaStream && !tapped.has(stream)) {
          tapped.add(stream);
          cleanups.push(
            tapStream(ctx, stream, {
              onSpeechStart: () => {
                const off = lastMicOffRef.current;
                if (off === null) return;
                lastMicOffRef.current = null;
                const gap = performance.now() - off;
                setGaps((g) => [...g.slice(-7), gap]);
              },
            }),
          );
        }
      }
    }, 250);

    return () => {
      document.removeEventListener("pointerdown", resume);
      clearInterval(domPoll);
      cleanups.forEach((fn) => fn());
      ctx.close();
      ctxRef.current = null;
    };
  }, []);

  // Local side: tap the published mic track (arrives after connect).
  useEffect(() => {
    const ctx = ctxRef.current;
    const track = microphoneTrack?.track?.mediaStreamTrack;
    if (!ctx || !track) return;
    return tapStream(ctx, new MediaStream([track]), {
      onSpeechEnd: (t) => {
        lastMicOffRef.current = t;
      },
    });
  }, [microphoneTrack]);

  const sorted = [...gaps].sort((a, b) => a - b);
  const p50 = sorted.length ? sorted[Math.floor((sorted.length - 1) / 2)] : null;

  return (
    <div
      data-testid="latency-hud"
      className="fixed right-2 top-2 z-50 rounded-lg bg-slate-950/80 px-3 py-2 font-mono text-[11px] leading-relaxed text-emerald-300"
    >
      <div className="text-slate-400">reply gap ms</div>
      {gaps.length === 0 ? (
        <div className="text-slate-500">ask something…</div>
      ) : (
        <>
          {gaps.map((g, i) => (
            <div key={i}>{g.toFixed(0)}</div>
          ))}
          <div className="border-t border-slate-700 text-emerald-200">p50 {p50?.toFixed(0)}</div>
        </>
      )}
    </div>
  );
}
