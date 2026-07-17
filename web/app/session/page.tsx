"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useCallback, useState } from "react";
import { PushToTalkButton } from "@/components/PushToTalkButton";

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantToken: string;
};

export default function SessionPage() {
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setConnecting(true);
    setError(null);
    try {
      const res = await fetch("/api/token", { method: "POST" });
      if (!res.ok) throw new Error(`token request failed: ${res.status}`);
      setDetails(await res.json());
    } catch {
      setError("Couldn't reach mission control. Try again in a moment!");
    } finally {
      setConnecting(false);
    }
  }, []);

  if (!details) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-950 text-white">
        <h1 className="text-4xl font-bold">🚀 Commander Sky</h1>
        <button
          onClick={start}
          disabled={connecting}
          className="rounded-full bg-emerald-500 px-10 py-5 text-2xl font-bold shadow-xl transition-transform active:scale-95 disabled:opacity-50"
        >
          {connecting ? "Calling the station…" : "Talk to Commander Sky!"}
        </button>
        {error && <p className="text-amber-300">{error}</p>}
      </main>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={details.serverUrl}
      token={details.participantToken}
      connect
      audio={false} // mic stays off until the talk button enables it
      video={false} // we never use the child's camera
      onDisconnected={() => setDetails(null)}
      className="flex min-h-screen flex-col items-center justify-between bg-slate-950 py-8 text-white"
    >
      <AvatarView />
      <PushToTalkButton />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

/** Renders the avatar's video track fullscreen-ish; friendly idle text until it joins. */
function AvatarView() {
  const tracks = useTracks([Track.Source.Camera], { onlySubscribed: true });
  const avatarTrack = tracks[0];

  if (!avatarTrack) {
    return (
      <div className="flex flex-1 items-center justify-center text-2xl text-slate-300">
        <span className="animate-bounce">🧑‍🚀 Commander Sky is floating over…</span>
      </div>
    );
  }
  return (
    <VideoTrack
      trackRef={avatarTrack}
      className="max-h-[70vh] flex-1 rounded-3xl object-contain"
    />
  );
}
