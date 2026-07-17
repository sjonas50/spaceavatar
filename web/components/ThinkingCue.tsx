"use client";

/**
 * Latency-masking cue while the response generates. Product rule: never show
 * a spinner — thinking looks like twinkling stars, not loading.
 */
export function ThinkingCue() {
  return (
    <div
      aria-label="Commander Sky is thinking"
      className="flex items-center gap-3 text-3xl"
      data-testid="thinking-cue"
    >
      <span className="animate-bounce [animation-delay:0ms]">✨</span>
      <span className="animate-bounce [animation-delay:150ms]">⭐</span>
      <span className="animate-bounce [animation-delay:300ms]">✨</span>
    </div>
  );
}
