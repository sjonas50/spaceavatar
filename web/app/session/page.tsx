"use client";

import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import { useCallback, useState } from "react";
import { AvatarView } from "@/components/AvatarView";
import { PushToTalkButton } from "@/components/PushToTalkButton";
import { buildConnectOptions } from "@/lib/livekit";

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
        <div className="animate-[float_3s_ease-in-out_infinite] text-8xl">🧑‍🚀</div>
        <h1 className="text-4xl font-bold">Commander Sky</h1>
        <button
          onClick={start}
          disabled={connecting}
          data-testid="start-session"
          className="rounded-full bg-emerald-500 px-10 py-5 text-2xl font-bold shadow-xl transition-transform active:scale-95 disabled:opacity-50"
        >
          {connecting ? "Calling the station…" : "Talk to Commander Sky!"}
        </button>
        {error && (
          <p className="text-amber-300" data-testid="session-error">
            {error}
          </p>
        )}
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
      connectOptions={buildConnectOptions()}
      onDisconnected={() => setDetails(null)}
      className="flex min-h-screen flex-col items-center justify-between bg-slate-950 py-8 text-white"
    >
      <AvatarView />
      <div className="pb-4">
        <PushToTalkButton />
      </div>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}
