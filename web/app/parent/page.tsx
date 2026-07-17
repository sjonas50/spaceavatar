import { ParentGate } from "@/components/ParentGate";

export default function ParentPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-950 p-8 text-white">
      <ParentGate>
        <section className="flex max-w-md flex-col gap-4">
          <h1 className="text-3xl font-bold">Parent settings</h1>
          <p className="text-slate-300">
            Sessions end automatically after 15 minutes with a friendly goodbye. The
            microphone is only active while the talk button is pressed, no audio or
            conversation transcripts are stored, and Commander Sky never asks for
            personal information.
          </p>
          <p className="text-slate-400 text-sm">
            Questions? See our privacy policy (coming with launch) or contact us.
          </p>
        </section>
      </ParentGate>
    </main>
  );
}
