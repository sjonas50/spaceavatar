# Turn-Latency Baseline

Measured with `web/e2e/latency-probe.mjs` (synthesized spoken questions as the
fake mic capture) against the local agent in `AVATAR_MODE=none`, idle behaviors
disabled, `ENDPOINTING_DELAY_S=0.5`. Numbers come from the agent's
`turn_latency` log lines (serial path: eou + guard + LLM TTFT + TTS TTFB).

## Baseline — 2026-08-12 (pre-U1, `33fe2e7`)

| turn | total_ms | guard_ms | ttft_ms | ttfb_ms |
|---|---|---|---|---|
| 1 | 1171 | 0 | 1087 | 83 |
| 2 | 1674 | 525 | 1063 | 85 |
| 3 | 1713 | 397 | 1166 | 149 |
| 4 | 2367 | 670 | 1532 | 165 |
| 5 | 1428 | 32 | 1260 | 135 |
| 6 | 1718 | 503 | 1120 | 94 |

**p50 ≈ 1,694ms · p95 ≈ 2,205ms** (6 turns)

Reading:
- **LLM TTFT is the dominant term** (1.06–1.53s, ~70% of the median turn).
- **Guard is high-variance** (0–670ms): speculation sometimes covers it
  entirely, often not — exactly the U1.2 target.
- TTS TTFB is healthy (83–165ms, Cartesia WebSocket warm).

Caveats:
- In Flux STT-driven turn mode, `EOUMetrics.end_of_utterance_delay` reads ~0 —
  the real silence→end-of-turn wait (~0.5s configured) happens inside Flux and
  is **not** included in these totals. Perceived latency ≈ total_ms + ~0.5s.
- `AVATAR_MODE=none`: Anam adds its transport tail (~150ms class) on top.
- Single machine, single session, same-day network — treat deltas ≥100ms as
  signal, smaller as noise.

## U1 exit criteria (same probe, same questions)

- guard p50 < 150ms, speculative-hit rate > 80%
- turn e2e p50 ≤ 1,500ms — implies TTFT p50 ≤ ~1,200ms after the prompt diet

## After U1 — 2026-08-12 (same probe) — GATE PASSED

| turn | total_ms | guard_ms | ttft_ms | ttfb_ms |
|---|---|---|---|---|
| 1 | 1852 | 535 | 1221 | 96 |
| 2 | 1526 | 102 | 1254 | 168 |
| 3 | 1722 | 406 | 1208 | 108 |
| 4 | 1411 | 0 | 1313 | 97 |
| 5 | 1307 | 45 | 1110 | 151 |
| 6 | 1082 | 11 | 948 | 123 |

**p50 ≈ 1,469ms (−225) · p95 ≈ 1,826ms (−379) · speculative-hit 6/6 ·
guard p50 ≈ 73ms** ✓ all criteria met.

What changed and what didn't:
- **Speculation key now strips punctuation/casing** — interim transcripts
  ("how does gps work") match finals ("How does GPS work?"). Hit rate went
  ~50% → 100%; residual guard time is awaiting a still-in-flight speculation,
  not re-classifying (turns 1/3: question asked early in the audio gap).
- **Guard prompt caching skipped (planned U1.1):** the classifier prompt is
  ~300 tokens — below Anthropic's minimum cacheable prefix. No-op; the
  speculation fix was the real lever.
- **Prompt diet skipped (planned U1.4):** measured system prompt is ~3.5k
  tokens (the plan's "20k" was a cumulative session counter misread). LLM
  cache telemetry (new `prompt_cached_tokens` field) confirms >90% of the
  prompt is served from cache.
- Remaining dominant term is **Sonnet TTFT (~1.0–1.3s)** — irreducible
  without a model change, which is out of scope (persona quality).

## Perceived latency + Anam gates — 2026-08-12 (probe v2)

Probe v2 measures what the visitor actually experiences: it taps the fake-mic
stream and every remote audio element with WebAudio RMS monitors, logging end
of spoken question → response audio onset in the browser. With the avatar,
remote audio is Anam's republished track synced to video, so audio onset ≈
lips moving. A wall-clock anchor aligns browser events with agent log lines.
Turn 1 of each run is discarded (question plays during connect + greeting);
turns 2–6 are the sample. Local agent, local `next dev`, same machine.

### Perceived gap: question end → response audible (ms)

| run | t2 | t3 | t4 | t5 | t6 | p50 |
|---|---|---|---|---|---|---|
| `anam` | 5385 | 3711 | 4711 | 4561 | 3839 | **4561** |
| `none` (control 1) | 4606 | 3929 | 5429 | 3580 | 5180 | **4606** |
| `none` (control 2, aligned) | 3865 | 3566 | 4668 | 4667 | 3644 | **3865** |

### Decomposition (control 2, clock-aligned per turn)

| turn | flux_wait | serial path | delivery | perceived |
|---|---|---|---|---|
| 2 | 943 | 2123 | 798 | 3865 |
| 3 | 1115 | 1039 | 1413 | 3566 |
| 4 | 1187 | 1264 | 2217 | 4668 |
| 5 | 966 | 1123 | 2578 | 4667 |
| 6 | 896 | 1683 | 1066 | 3644 |

- **flux_wait** = mic energy end → agent EOU (guard-verdict timestamp).
  Configured `ENDPOINTING_DELAY_S=0.5`; **measured ~1.0s median** — the
  baseline's "~0.5s" assumption was optimistic by 2×.
- **serial path** = the existing `turn_latency` total (guard + TTFT + TTFB).
- **delivery** = TTS first byte at the agent → audible in the browser
  (LiveKit publish + subscriber jitter buffer + playout). **0.8–2.6s, median
  ~1.4s — previously invisible to all agent-side timers** and the largest
  new finding. High variance; needs its own investigation (jitter-buffer
  tuning, or headless-Chromium playout artifact — see caveats).

### Gate verdicts (research.md trial gates 2 & 3)

- **Gate 2 — utterance end → avatar speaking vs 1.2s budget: FAIL, but not
  Anam's fault.** Perceived p50 ≈ 4.6s. The none-mode control fails the same
  budget at the same magnitude; the avatar's marginal cost (anam p50 − none
  p50) is −45ms…+700ms across controls — **within run-to-run noise (≲0.5s)**.
- **Gate 3 — BYO-TTS (Cartesia → Anam) tail vs ~150ms claim: not resolvable
  at n=5, but no gross penalty.** The passthrough path adds at most the noise
  bound above; the claim is neither confirmed nor refuted.
- Where the 1.2s budget actually goes: ~1.0s Flux EOT + ~1.3s serial
  (Sonnet-dominated) + ~1.4s delivery. **The budget is unmeetable without
  attacking Flux EOT and the delivery path**; the avatar choice is currently
  irrelevant to latency.

### Caveats

- n=5 per run, single machine, same-day network; deltas <500ms between runs
  are noise at this sample size.
- Headless Chromium (software decode, null audio sink) may not match real
  device jitter-buffer behavior — validate the ~1.4s delivery figure once on
  a real iPad before optimizing against it.
- Probe questions are synthesized TTS (`say -v Samantha`) — Flux EOT timing
  on real human prosody may differ.
- Probe lead-in is 2s; connect + greeting takes ~6–17s, so turn 1 is always
  lost. Next probe build: use ~20s lead-in silence.
