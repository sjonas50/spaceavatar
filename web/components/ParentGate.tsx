"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const HOLD_MS = 3000;

type Stage = "hold" | "math" | "open";

/**
 * Adult-verification gate in front of settings: hold a button for 3 seconds,
 * then answer an arithmetic question. Deliberately tedious for small kids.
 */
export function ParentGate({ children }: { children: React.ReactNode }) {
  const [stage, setStage] = useState<Stage>("hold");

  if (stage === "open") return <>{children}</>;
  return stage === "hold" ? (
    <HoldStep onDone={() => setStage("math")} />
  ) : (
    <MathStep onDone={() => setStage("open")} />
  );
}

function HoldStep({ onDone }: { onDone: () => void }) {
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    startedAtRef.current = null;
    setProgress(0);
  }, []);

  const start = useCallback(() => {
    startedAtRef.current = Date.now();
    timerRef.current = setInterval(() => {
      const started = startedAtRef.current;
      if (started === null) return;
      const elapsed = Date.now() - started;
      setProgress(Math.min(1, elapsed / HOLD_MS));
      if (elapsed >= HOLD_MS) {
        stop();
        onDone();
      }
    }, 50);
  }, [onDone, stop]);

  useEffect(() => stop, [stop]);

  return (
    <div className="flex flex-col items-center gap-6">
      <h2 className="text-2xl font-bold">Grown-ups only</h2>
      <p className="text-slate-300">Press and hold the button for 3 seconds.</p>
      <button
        data-testid="hold-button"
        onPointerDown={start}
        onPointerUp={stop}
        onPointerLeave={stop}
        className="relative h-28 w-28 overflow-hidden rounded-full bg-indigo-500 text-lg font-bold"
      >
        <span
          className="absolute inset-x-0 bottom-0 bg-indigo-300/60 transition-[height]"
          style={{ height: `${progress * 100}%` }}
        />
        <span className="relative">Hold</span>
      </button>
    </div>
  );
}

function MathStep({ onDone }: { onDone: () => void }) {
  // Generated once per mount; randomness keeps kids from memorizing the answer.
  const [question] = useState(() => {
    const a = 3 + Math.floor(Math.random() * 6);
    const b = 4 + Math.floor(Math.random() * 5);
    return { a, b };
  });
  const [answer, setAnswer] = useState("");
  const [wrong, setWrong] = useState(false);

  const check = useCallback(() => {
    if (Number(answer) === question.a + question.b) {
      onDone();
    } else {
      setWrong(true);
      setAnswer("");
    }
  }, [answer, question, onDone]);

  return (
    <div className="flex flex-col items-center gap-6">
      <h2 className="text-2xl font-bold">One more check</h2>
      <p className="text-xl" data-testid="math-question">
        What is {question.a} + {question.b}?
      </p>
      <div className="flex gap-3">
        <input
          data-testid="math-answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          inputMode="numeric"
          className="w-24 rounded-xl bg-slate-800 px-4 py-3 text-center text-xl"
          aria-label="Answer"
        />
        <button
          data-testid="math-submit"
          onClick={check}
          className="rounded-xl bg-indigo-500 px-6 py-3 font-bold"
        >
          Go
        </button>
      </div>
      {wrong && <p className="text-amber-300">Not quite — try again.</p>}
    </div>
  );
}
