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
