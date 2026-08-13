"use client";

import { useLocalParticipant, useRoomContext } from "@livekit/components-react";
import type { RemoteAudioTrack } from "livekit-client";
import { ParticipantEvent } from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";

const RMS_ON = 0.01;
const RTP_LEVEL_ON = 0.01;
const POLL_MS = 25;
const HANGOVER_MS = 700;

/**
 * On-device perceived-latency HUD, enabled with `?lat=1`. Pairs end-of-question
 * with response onset, like probe v2 (web/e2e/latency-probe.mjs), but with
 * device-portable detection: iOS Safari renders *silence* when a remote WebRTC
 * stream is fed into Web Audio, so the remote side reads RTP audio levels from
 * RTCRtpReceiver.getSynchronizationSources() instead, and both sides fall back
 * to LiveKit isSpeaking events (server-driven, works everywhere, ±ums coarser).
 * The "you/her" dots show live detection per side — if a side never lights up,
 * that detection path is broken on this device.
 * Numbers only: no speech content, nothing persisted or transmitted.
 */
export function LatencyHud() {
  const room = useRoomContext();
  const { localParticipant, microphoneTrack } = useLocalParticipant();
  const [gaps, setGaps] = useState<number[]>([]);
  const [youActive, setYouActive] = useState(false);
  const [herActive, setHerActive] = useState(false);
  const [modes, setModes] = useState({ mic: "spk", her: "spk" });
  const ctxRef = useRef<AudioContext | null>(null);
  const lastMicOffRef = useRef<number | null>(null);
  // True once the precise path has heard real signal — gates the coarse
  // isSpeaking fallback so the two detectors never fight over timestamps.
  const micRmsLiveRef = useRef(false);
  const herRtpLiveRef = useRef(false);

  const completeGap = useCallback((onset: number) => {
    const off = lastMicOffRef.current;
    if (off === null) return;
    lastMicOffRef.current = null;
    setGaps((g) => [...g.slice(-7), onset - off]);
  }, []);

  // Remote side: poll RTP audio levels across all remote audio receivers.
  useEffect(() => {
    let speaking = false;
    let lastAbove = 0;
    const timer = setInterval(() => {
      let level = 0;
      let sawLevel = false;
      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.audioTrackPublications.values()) {
          const receiver = (pub.track as RemoteAudioTrack | undefined)?.receiver;
          if (!receiver?.getSynchronizationSources) continue;
          for (const s of receiver.getSynchronizationSources()) {
            if (typeof s.audioLevel === "number") {
              sawLevel = true;
              level = Math.max(level, s.audioLevel);
            }
          }
        }
      }
      if (sawLevel && !herRtpLiveRef.current) {
        herRtpLiveRef.current = true;
        setModes((m) => ({ ...m, her: "rtp" }));
      }
      const now = performance.now();
      if (level > RTP_LEVEL_ON) {
        if (!speaking) {
          speaking = true;
          setHerActive(true);
          completeGap(now);
        }
        lastAbove = now;
      } else if (speaking && now - lastAbove > HANGOVER_MS) {
        speaking = false;
        setHerActive(false);
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [room, completeGap]);

  // Mic side: Web Audio RMS on the published mic track (local capture is the
  // one Web Audio path iOS does render).
  useEffect(() => {
    const track = microphoneTrack?.track?.mediaStreamTrack;
    if (!track) return;
    const ctx = ctxRef.current ?? new AudioContext();
    ctxRef.current = ctx;
    const resume = () => void ctx.resume();
    document.addEventListener("pointerdown", resume);
    resume();
    const src = ctx.createMediaStreamSource(new MediaStream([track]));
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
      if (rms > RMS_ON) {
        if (!micRmsLiveRef.current) {
          micRmsLiveRef.current = true;
          setModes((m) => ({ ...m, mic: "rms" }));
        }
        if (!speaking) {
          speaking = true;
          setYouActive(true);
        }
        lastAbove = now;
      } else if (speaking && now - lastAbove > HANGOVER_MS) {
        speaking = false;
        setYouActive(false);
        lastMicOffRef.current = lastAbove;
      }
    }, POLL_MS);
    return () => {
      document.removeEventListener("pointerdown", resume);
      clearInterval(timer);
      src.disconnect();
    };
  }, [microphoneTrack]);

  useEffect(
    () => () => {
      ctxRef.current?.close();
      ctxRef.current = null;
    },
    [],
  );

  // Coarse fallback, both sides: LiveKit isSpeaking events. Only acts while
  // the precise path for that side has never seen signal.
  useEffect(() => {
    const onLocal = (speaking: boolean) => {
      if (micRmsLiveRef.current) return;
      setYouActive(speaking);
      if (!speaking) lastMicOffRef.current = performance.now();
    };
    localParticipant?.on(ParticipantEvent.IsSpeakingChanged, onLocal);

    const remoteHandlers = new Map<string, (speaking: boolean) => void>();
    const watchRemotes = setInterval(() => {
      for (const p of room.remoteParticipants.values()) {
        if (remoteHandlers.has(p.identity)) continue;
        const handler = (speaking: boolean) => {
          if (herRtpLiveRef.current) return;
          setHerActive(speaking);
          if (speaking) completeGap(performance.now());
        };
        remoteHandlers.set(p.identity, handler);
        p.on(ParticipantEvent.IsSpeakingChanged, handler);
      }
    }, 500);

    return () => {
      localParticipant?.off(ParticipantEvent.IsSpeakingChanged, onLocal);
      clearInterval(watchRemotes);
      for (const [identity, handler] of remoteHandlers) {
        room.remoteParticipants.get(identity)?.off(ParticipantEvent.IsSpeakingChanged, handler);
      }
    };
  }, [room, localParticipant, completeGap]);

  const sorted = [...gaps].sort((a, b) => a - b);
  const p50 = sorted.length ? sorted[Math.floor((sorted.length - 1) / 2)] : null;

  const dot = (active: boolean) =>
    `inline-block h-2 w-2 rounded-full ${active ? "bg-emerald-400" : "bg-slate-600"}`;

  return (
    <div
      data-testid="latency-hud"
      className="fixed right-2 top-2 z-50 rounded-lg bg-slate-950/80 px-3 py-2 font-mono text-[11px] leading-relaxed text-emerald-300"
    >
      <div className="flex items-center gap-2 text-slate-400">
        <span className={dot(youActive)} /> you:{modes.mic}
        <span className={dot(herActive)} /> her:{modes.her}
      </div>
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
