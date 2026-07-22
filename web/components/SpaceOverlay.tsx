"use client";

import { useDataChannel, useLocalParticipant } from "@livekit/components-react";
import { ParticipantEvent } from "livekit-client";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";

type ShowImage = { type: "show_image"; id: string; src: string; caption: string };

const DISMISS_MS = 25_000;

const ALLOWED_SRC = (src: string) =>
  src.startsWith("/space/") || src.startsWith("https://images-assets.nasa.gov/image/");

/**
 * Renders pictures the agent pushes over the "ui" data channel while talking.
 * Sources are allowlisted: the local gallery and NASA's public archive only.
 * Dismisses on tap, after a timer, or as soon as the visitor starts speaking
 * (a stale picture shouldn't hang over a new question).
 */
export function SpaceOverlay() {
  const [image, setImage] = useState<ShowImage | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { localParticipant } = useLocalParticipant();

  const onMessage = useCallback((msg: { payload: Uint8Array }) => {
    let parsed: ShowImage;
    try {
      parsed = JSON.parse(new TextDecoder().decode(msg.payload));
    } catch {
      return;
    }
    if (parsed.type !== "show_image" || !ALLOWED_SRC(parsed.src ?? "")) return;
    setImage(parsed);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setImage(null), DISMISS_MS);
  }, []);

  useDataChannel("ui", onMessage);

  // Visitor started talking (new question or barge-in) — clear the old picture.
  useEffect(() => {
    if (!localParticipant) return;
    const onSpeaking = (speaking: boolean) => {
      if (speaking) setImage(null);
    };
    localParticipant.on(ParticipantEvent.IsSpeakingChanged, onSpeaking);
    return () => {
      localParticipant.off(ParticipantEvent.IsSpeakingChanged, onSpeaking);
    };
  }, [localParticipant]);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  if (!image) return null;
  return (
    <button
      aria-label={`Dismiss picture: ${image.caption}`}
      onClick={() => setImage(null)}
      className="absolute right-4 top-4 z-10 w-[42vw] max-w-md overflow-hidden rounded-2xl border border-cyan-400/25 bg-slate-950/85 shadow-[0_0_50px_rgba(34,211,238,0.15)] backdrop-blur transition-transform hover:scale-[1.02]"
    >
      <Image
        src={image.src}
        alt={image.caption}
        width={640}
        height={480}
        className="h-auto w-full object-cover"
        priority
        onError={() => setImage(null)} // broken asset: vanish, don't show a dead frame
      />
      <div className="px-4 py-3 text-left">
        <p className="font-mono text-[10px] uppercase tracking-widest text-cyan-400/70">
          Mission archive
        </p>
        <p className="text-sm text-slate-200">{image.caption}</p>
      </div>
    </button>
  );
}
