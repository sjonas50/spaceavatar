"use client";

import { useEffect, useState } from "react";

const STEPS = [
  "ESTABLISHING UPLINK",
  "ACQUIRING ORBITAL SIGNAL",
  "SYNCING VIDEO FEED",
  "COMMANDER SKY INBOUND",
];

/**
 * Masks connection + avatar spin-up (a few seconds of LemonSlice session
 * boot) as an intentional comms boot sequence instead of dead air.
 */
export function TransmissionBoot({ compact = false }: { compact?: boolean }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(
      () => setStep((s) => Math.min(s + 1, STEPS.length - 1)),
      1800,
    );
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      data-testid="transmission-boot"
      className={`flex flex-col gap-2 font-mono text-cyan-300/90 ${compact ? "text-xs" : "text-sm"}`}
    >
      {STEPS.slice(0, step + 1).map((label, i) => (
        <p key={label} className={i === step ? "blinking-cursor" : "text-cyan-500/60"}>
          {i < step ? "✓" : "▸"} {label}
        </p>
      ))}
    </div>
  );
}
