# Research: Commander Sky — Real-Time Astronaut Avatar for Kids

**Date:** 2026-07-17 · **Status:** Research phase complete · **Input:** `BUILD_PLAN.md` v1.0

## Executive Summary

The build plan's core architecture (LiveKit Agents + swappable avatar plugin + Claude + streaming STT/TTS) is validated and current — LiveKit Agents 1.6.5 (July 9, 2026) is the right orchestration layer with 15 first-party avatar plugins. **One critical conflict: Anam's CARA-4 model is photoreal-only, but the plan requires a stylized, non-photoreal character.** LemonSlice is the only LiveKit-native avatar plugin explicitly supporting cartoon/stylized avatars; a frontend-rendered 3D character (Three.js + viseme stream) is the strategic alternative that also eliminates avatar per-minute cost and the biggest COPPA exposure. Two stack updates since the plan was drafted: Deepgram **Flux** (not Nova-3) is now the agent-optimized STT with fused turn detection, and ElevenLabs carries both ToS risk (children's voice-data prohibition needs written legal confirmation) and reliability concerns (10 incidents in 28 days, Feb 2026). The $0.15–0.30/min cost estimate holds (~$0.165/min validated at Growth-tier pricing).

## Problem Statement

Build a browser web app where kids ages 5–10 hold live voice conversations with an animated astronaut character teaching about Neil Armstrong, Apollo, and space — with hard latency targets (≤1.2s p50 utterance-end → first audio), a launch-blocking safety layer, and COPPA-compliant no-retention architecture.

## Technology Evaluation

### Orchestration (confirmed)

| Rank | Framework | Version (date) | Verdict |
|---|---|---|---|
| 1 | **LiveKit Agents** | 1.6.5 (Jul 9, 2026), Py 3.10–3.14 | ✅ Keep. 15 avatar plugins, first-party Anthropic plugin (defaults `claude-sonnet-4-6`), Turn Detector v1.0 (fused audio+text end-of-turn). |
| 2 | Pipecat | 1.5.0 (Jul 4, 2026) | Fallback only. Fewer avatar options; Anam support is community-maintained. |
| 3 | Vapi | managed | Avoid. No avatar abstraction; can't intercept transcripts pre-LLM (kills the input guard). |

### Avatar — ⚠️ plan change required

| Rank | Provider | Plugin ver. | Latency | Stylized? | Verdict |
|---|---|---|---|---|---|
| 1 | **LemonSlice** | 1.5.12 (May 21 — lags core) | "medium," <3s | **Yes — only one** | Primary candidate. Cartoon/mascot avatars from a single image; already marketed for kids' tutoring. |
| 1b | **Frontend 3D character** (Three.js/Spline + viseme stream) | n/a | Best (local render) | Yes, full control | Strategic alternative: no avatar vendor, no per-minute avatar cost, no child biometrics leaving the device. More frontend engineering. |
| 2 | HeyGen LiveAvatar | 1.6.5 | medium | No | Photoreal fallback; extra WS hop. |
| 3 | Anam (CARA-4) | 1.6.5 | ~180ms, best-in-class | **No — photoreal only** | Wrong for this product. Custom avatars require real photos; 5-session cap on Growth (~$0.12/min); ZDR Enterprise-only; processes child facial+voice biometrics = highest COPPA exposure in stack. Use only if product pivots to photoreal. |
| 4 | Tavus / Simli / bitHuman / D-ID | 1.6.5 | varies | No | Tavus $0.37/min; Simli has visible quality artifacts; none stylized. |

### STT

| Rank | Provider | Price | Verdict |
|---|---|---|---|
| 1 | **Deepgram Flux** (`flux-general-en`, GA Apr 2026) | $0.0065/min | Fused transcription + turn detection saves 200–600ms vs Nova-3 + separate VAD. Use `keyterm` biasing (planet/astronaut vocab) and `mip_opt_out=true` on every request. |
| 2 | AssemblyAI Universal-3.5 Pro | comparable | Fallback if Flux underperforms on kid speech. |
| 3 | Deepgram Nova-3 | $0.0048/min | Batch/accuracy model, not agent-optimized. |

**Universal caveat:** no vendor publishes children's-speech benchmarks; academic work shows 2–3× WER degradation for ages 5–10 across all providers. Empirical testing with real kid audio in Phase 0 is mandatory (plan already says this — it's confirmed as the top technical risk).

### TTS

| Rank | Provider | P50 TTFA | Verdict |
|---|---|---|---|
| 1 | **Cartesia Sonic-3.5** | 188ms | 100ms faster than ElevenLabs in production; persistent WebSocket avoids per-turn HTTP overhead. Voice clone from 10s audio. (Sonic-2 EOL Jun 1, 2026.) |
| 2 | ElevenLabs Flash v2.5 | 288ms (tight IQR 28ms) | Best voice-design tooling. But: ToS prohibits under-18 users and submitting children's voice data (TTS *output* to kids is likely fine — get written confirmation); 10 incidents/28 days; no SLA below Enterprise. |
| 3 | Deepgram Aura-2 | 313ms | Compliance-simple fallback (same vendor as STT). |

**Hybrid play:** design the Commander Sky voice in ElevenLabs Voice Design, clone/port it to Cartesia for production serving.

## Architecture Patterns Found

- **Canonical avatar startup order** (official `livekit/agents/examples/avatar_agents`): create `AgentSession` → `avatar.start(session, room)` → `await avatar.wait_for_join()` → `session.start(..., room_output_options=RoomOutputOptions(audio_enabled=False))`. The `audio_enabled=False` prevents double audio (avatar republishes TTS synced to video). Note: the build plan's Anam-specific "session before avatar" warning reflects an older API — current official docs say avatar-first; verify against current plugin in Phase 0.
- **Safety hook location:** `on_user_turn_completed` callback — after STT, before LLM context injection (webrtc.ventures guardrails pattern). Redact/replace rather than block; no off-the-shelf kids classifier exists — use a fast Claude Haiku call as synchronous input guard (~100–200ms).
- **Kid-tuned turn-taking:** raise `min_delay` to 0.8–1.0s (kids' mid-thought pauses routinely exceed 800ms; default 0.3s is far too aggressive), `min_words=3` for barge-in, longer `false_interruption_timeout` (~1.2s). Known bug context: endpointing delays stack differently in STT-mode vs VAD-mode (livekit/agents #4325, #5669) — with Flux's native end-of-turn, set LiveKit `min_delay=0` and let Flux control timing (verify no double-firing with Turn Detector v1.0).
- **Latency budget is achievable:** tuned cascaded pipelines hit ~400ms p50 / ~650ms p95 (STT 60–120ms + LLM TTFT 100–250ms with prompt caching + TTS first-chunk 60–100ms + WebRTC 20–60ms). The unknown is LemonSlice's "<3s" avatar latency — this could blow the ≤1.2s p50 target and must be measured in Phase 0.
- **Prod reference infra:** AWS Tavus/Pipecat sample (ECS Fargate, SSM secrets, path-scoped CI); HeyGen starter shows clean `agent.py`/`pipeline.py`/`worker.py` split and `prewarm()` pattern.

## Key APIs & Services (validated pricing, Jul 2026)

| Service | Cost | Concurrency | Retention/COPPA | Risk |
|---|---|---|---|---|
| Avatar (Anam Growth ref.) | $0.12/min | 5 sessions | ZDR Enterprise-only; child biometrics | **High** |
| LiveKit Cloud | ~$0.011/min (Ship $50/mo min — Build plan has 10–20s cold starts) | Build: 5 agents | DPA available; zero-retention in transit | Med |
| Deepgram Flux | $0.0065/min | 150 streams PAYG | `mip_opt_out=true` + DPA | Med |
| TTS | ~$0.02/min | ElevenLabs: 10–40 by tier, hard cap, no auto-retry | ElevenLabs ToS ambiguity | High (11L) / Low (Cartesia — verify) |
| Claude API | ~$0.007/min w/ caching | tier-based | **Cleanest in stack:** ZDR available, never trains on API data, minors guidance published | Low |

**Total: ~$0.165/min** — validates the plan's $0.15–0.30 range. A frontend-rendered avatar removes the dominant $0.12/min line entirely (→ ~$0.05/min).

## Known Pitfalls & Risks

1. **Anam ≠ stylized.** The plan's Phase 3 ("stylized-not-photoreal, design in Anam Lab") is not possible on Anam. Decide LemonSlice vs frontend-3D in Phase 0.
2. **COPPA amended rule (eff. 2025):** voiceprints/facial templates are now explicitly PII; AI-training consent must be separate; a written retention policy is required. Cloud avatar providers that ingest child audio/video are the largest exposure — another argument for frontend rendering.
3. **ElevenLabs ToS:** under-18 user prohibition + children's voice-data prohibition. TTS-output-only is likely permissible but needs written confirmation — or sidestep via Cartesia.
4. **LemonSlice plugin lags core** (1.5.12 vs 1.6.5) and has no granular latency benchmark or public kids-production case study.
5. **iPad/school networks:** UDP blocking (~15–20% failure without TURN) and iCloud Private Relay interfere with WebRTC. Force TURN relay; test iPadOS Safari explicitly — kids are disproportionately on iPads.
6. **Cold starts:** LiveKit Build plan (10–20s) is a UX showstopper; Ship plan minimum, co-locate Fly.io workers with the LiveKit cluster region.
7. **Claude Sonnet 5 tokenizer** emits ~30% more tokens than 4.6 — revalidate cost if upgrading; intro pricing ($2/$10 per MTok) ends Aug 31, 2026.
8. **ElevenLabs overages** ($1,320/block on Scale) — hard spend caps if used.

## Recommended Stack (opinionated)

| Layer | Pick | Change vs plan |
|---|---|---|
| Orchestration | LiveKit Agents 1.6.5 + LiveKit Cloud (Ship) | none |
| Avatar | **LemonSlice** (prototype Wk 1) with **frontend Three.js character** as the strategic alternative; Anam only if pivoting photoreal | **changed** |
| LLM | Claude Sonnet 4.6 via `livekit-plugins-anthropic`, 1-hr prompt caching, ZDR via sales | refined |
| STT | **Deepgram Flux** `flux-general-en`, keyterm biasing, `mip_opt_out=true` | changed (was Nova) |
| TTS | **Cartesia Sonic-3.5** (voice designed in ElevenLabs, ported) | changed |
| Turn-taking | Flux native end-of-turn, kid-tuned delays (0.8–1.0s), `min_words=3` barge-in | refined |
| Safety | `on_user_turn_completed` input guard (Claude Haiku sync check) + output validator pre-TTS | pattern confirmed |
| Frontend | Next.js + LiveKit client SDK, TURN-forced ICE for school networks | refined |

Phase 0 becomes a **bake-off**: LemonSlice vs frontend-3D on (a) measured end-to-end latency vs the 1.2s budget, (b) avatar charm with 2–3 kids, (c) engineering cost. If LemonSlice's latency or quality disappoints, frontend rendering wins on every other axis (latency, cost, COPPA).

## Open Questions

1. LemonSlice real-world p50/p95 latency and any kids-production case study — measure ourselves in Phase 0.
2. Does Deepgram Flux end-of-turn conflict/double-fire with LiveKit Turn Detector v1.0?
3. ElevenLabs written confirmation that TTS-to-child-listeners is ToS-compliant (only needed if voice-design path is used).
4. Cartesia data-retention/DPA posture for child-adjacent use (not yet audited — do before Phase 2).
5. Anam plugin startup ordering: plan says session-first, current official docs say avatar-first — resolve against live plugin if Anam is ever used.
6. Will a `livekit-plugins-lemonslice` 1.6.x release land to close the version gap?

## Sources

- LiveKit Agents releases: https://github.com/livekit/agents/releases · avatar examples: https://github.com/livekit/agents/tree/main/examples/avatar_agents
- Avatar docs: https://docs.livekit.io/agents/models/avatar/ · LemonSlice plugin: https://docs.livekit.io/agents/models/avatar/plugins/lemonslice/ · PyPI: https://pypi.org/project/livekit-plugins-lemonslice/
- Anam custom avatars (photoreal reqs): https://anam.ai/docs/concepts/custom-avatars · pricing: https://anam.ai/pricing · DPA: https://anam.ai/data-processing
- Avatar provider eval: https://www.docket.io/blog/heygen-vs-tavus-vs-anam-vs-simli-how-we-chose-dockets-ai-avatar-provider · https://medium.com/@ggarciabernardo/the-live-avatar-landscape-apis-transport-and-subjective-evaluation-of-10-leading-providers-5b5b6e8a54dc
- Deepgram Flux: https://deepgram.com/learn/introducing-flux-conversational-speech-recognition · pricing: https://deepgram.com/pricing · MIP opt-out: https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program
- TTS benchmarks: https://gradium.ai/content/tts-latency-benchmark-2026 · Cartesia: https://docs.cartesia.ai/changelog/2026 · ElevenLabs models: https://elevenlabs.io/docs/overview/models · ToS: https://elevenlabs.io/terms-of-use · child-voice policy: https://help.elevenlabs.io/hc/en-us/articles/30183901911313
- Turn detection: https://livekit.com/blog/using-a-transformer-to-improve-end-of-turn-detection · issues: https://github.com/livekit/agents/issues/4325, /issues/5669
- Guardrails pattern: https://webrtc.ventures/2026/06/slug-voice-ai-security-webrtc-livekit-guardrails/
- Anthropic pricing/retention: https://platform.claude.com/docs/en/about-claude/pricing · minors guidance: https://support.claude.com/en/articles/9307344
- COPPA amendments: https://www.dataprotectionreport.com/2025/06/ftcs-coppa-rule-changes-include-ai-training-consent-requirement/ · FTC FAQ: https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions
- LiveKit pricing/limits: https://livekit.com/pricing · https://docs.livekit.io/deploy/admin/quotas-and-limits/
- WebRTC + Private Relay: https://webrtchacks.com/apples-not-so-private-relay-fails-with-webrtc/
