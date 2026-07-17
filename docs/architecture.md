# Architecture: Commander Sky

**Version:** 1.0 · July 2026  
**Status:** Design — pre-implementation

---

## 1. System Overview

Commander Sky is a real-time voice avatar web app. A child presses a button, speaks, and hears an animated astronaut character respond within ≤1.2s (p50). All processing runs server-side; no audio or transcript is persisted.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Kid's Browser (Next.js, iPad Safari first-class)                       │
│                                                                         │
│  [Push-to-Talk Button]  →  mic audio (WebRTC track, on press only)      │
│                                                                         │
│  Avatar render — TWO OPTIONS (swappable, decided in Phase 0 bake-off):  │
│    Option A: <LemonSlice video track>  ← avatar video from LiveKit Cloud│
│    Option B: <Three.js character>      ← local render, driven by audio  │
└───────────────┬──────────────────────────────────────────┬──────────────┘
                │  WebRTC (TURN-forced for school networks) │
                ▼                                           │
        ┌───────────────┐                                   │
        │ LiveKit Cloud │  (SFU, Ship plan, rooms)          │
        │ WebRTC SFU    │                                   │
        └───────┬───────┘                                   │
                │ audio track                               │
                ▼                                           │
  ┌─────────────────────────────────────────────────────┐   │
  │  Agent Worker (Fly.io, co-located with LK region)   │   │
  │                                                     │   │
  │  ┌──────────┐   transcript   ┌────────────────────┐ │   │
  │  │ Deepgram │ ─────────────► │  Input Guard       │ │   │
  │  │ Flux STT │  (end-of-turn  │  (Claude Haiku,    │ │   │
  │  │          │   native)      │   ~150ms sync)     │ │   │
  │  └──────────┘                └────────┬───────────┘ │   │
  │                                       │ safe / canned│   │
  │                                       ▼             │   │
  │                              ┌────────────────────┐ │   │
  │                              │  LLM               │ │   │
  │                              │  Claude Sonnet 4.6 │ │   │
  │                              │  (persona + facts  │ │   │
  │                              │   context, 1-hr    │ │   │
  │                              │   prompt caching)  │ │   │
  │                              └────────┬───────────┘ │   │
  │                                       │ text chunk  │   │
  │                                       ▼             │   │
  │                              ┌────────────────────┐ │   │
  │                              │  Output Guard      │ │   │
  │                              │  (regex + rules,   │ │   │
  │                              │   pre-TTS)         │ │   │
  │                              └────────┬───────────┘ │   │
  │                                       │ validated   │   │
  │                                       ▼             │   │
  │                              ┌────────────────────┐ │   │
  │                              │  Cartesia TTS      │ │   │
  │                              │  Sonic-3.5,        │ │   │
  │                              │  persistent WS     │ │   │
  │                              └────────┬───────────┘ │   │
  │                                       │ audio chunks│   │
  │                                       ▼             │   │
  │                           ┌─────────────────────┐   │   │
  │                           │  Avatar Adapter      │   │   │
  │                           │  avatar.py           │   │   │
  │                           │  ┌─────────────────┐ │   │   │
  │                           │  │ Option A:       │ │   │   │
  │                           │  │ LemonSlice      │─┼───┼──►│ video track
  │                           │  │ plugin (cloud)  │ │   │   │ → LiveKit
  │                           │  └─────────────────┘ │   │   │
  │                           │  ┌─────────────────┐ │   │   │
  │                           │  │ Option B:       │ │   │   │
  │                           │  │ viseme stream   │─┼───┼──►│ viseme msgs
  │                           │  │ → browser WS    │ │   │   │ → Three.js
  │                           │  └─────────────────┘ │   │   │
  │                           └─────────────────────┘   │   │
  └─────────────────────────────────────────────────────┘   │
                                                            │
        ┌──────────────────────────────────────────────┐    │
        │  Next.js Route Handler (token/session API)   │◄───┘
        │  Vercel edge function                        │
        │  Mints LiveKit access token + room grant     │
        └──────────────────────────────────────────────┘
```

---

## 2. Components

### Web Frontend
- **Purpose:** Child-facing UI. Push-to-talk mic control, avatar display, session lifecycle. Parent gate in front of settings.
- **Technology:** Next.js 15 App Router, `livekit-client` SDK, Tailwind CSS. iPad Safari is first-class target.
- **Inputs:** LiveKit access token from `/api/session` route. User audio on PTT press.
- **Outputs:** Audio track to LiveKit room. WebRTC room join/leave events.
- **Key decisions:** Push-to-talk over open mic — mic is only active while the button is held. This eliminates ambient audio capture (COPPA), reduces background-noise STT errors, and gives kids a clear interaction model. No typing anywhere. TURN-forced ICE (`iceTransportPolicy: "relay"`) handles UDP-blocked school networks and iCloud Private Relay. Avatar display is either the LiveKit video track (Option A) or a locally rendered Three.js character driven by viseme messages over a lightweight WebSocket (Option B).

### Token / Session API
- **Purpose:** Server-side LiveKit access token minting. The browser never holds API credentials.
- **Technology:** Next.js Route Handler (`/app/api/session/route.ts`) deployed on Vercel. Uses LiveKit Server SDK (Node).
- **Inputs:** HTTP POST from browser (optional: session preferences).
- **Outputs:** `{ token: string, url: string, roomName: string }`. Token carries `roomJoin` + `canPublish` grants and a TTL equal to `MAX_SESSION_MINUTES + 2` minutes.
- **Key decisions:** All API keys server-side only — `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` never reach the client. Room names are UUIDs; no user identifier is embedded.

### Agent Worker — `agent/src/commander_sky/main.py`
- **Purpose:** LiveKit Agents 1.6.5 worker. Wires `AgentSession` with STT, LLM, TTS, avatar adapter, and safety hooks.
- **Technology:** Python 3.12, `livekit-agents==1.6.5`, `livekit-plugins-deepgram`, `livekit-plugins-anthropic`, `livekit-plugins-cartesia`. Deployed on Fly.io machines, one worker process per session.
- **Inputs:** Audio track from LiveKit room. `AgentSession` lifecycle events.
- **Outputs:** Synthesized audio (and optionally avatar video) published back to the room.
- **Key decisions:** `prewarm()` hook pre-loads the persona prompt into the model context so prompt-cache hits are guaranteed from turn 1. Session timer enforces `MAX_SESSION_MINUTES` with a scripted sign-off message. Kid-tuned turn-taking: Flux native end-of-turn controls timing (`min_delay=0` in LiveKit Turn Detector to avoid double-firing), effective patience at 0.8–1.0s. Barge-in enabled with `min_words=3` threshold.

### Persona Module — `persona.py`
- **Purpose:** Builds the system prompt for Claude. Defines Commander Sky's character, tone, curriculum scope, and behavioral rules.
- **Technology:** Python string templating. Loads facts context from `facts/` at startup.
- **Inputs:** Facts markdown files from `agent/src/commander_sky/facts/`.
- **Outputs:** `str` system prompt injected into `AgentSession` LLM config.
- **Key decisions:** Prompt is static per session (enabling 1-hour prompt caching on Anthropic). Curriculum scope: Armstrong/Apollo 11, Moon, rockets, astronaut daily life, solar system. Responses constrained to 2–4 short sentences by prompt instruction. Deflection rule: off-topic → redirect to space without freeform discussion.

### Facts Content Module — `facts/`
- **Purpose:** Curated, versioned reference material injected into context. Keeps Claude grounded on historical accuracy.
- **Technology:** Markdown files in `agent/src/commander_sky/facts/`. Versioned in git. Human review gate before merging changes.
- **Inputs:** Static files at agent startup.
- **Outputs:** Text appended to persona system prompt by `persona.py`.

### Safety Module — `safety.py`
- **Purpose:** Dual-layer guard preventing unsafe content in either direction. Three sub-components.
- **Technology:** Python. Input guard uses `anthropic` SDK (Claude Haiku, synchronous call). Output guard is pure Python regex/rule checks (no external call, zero latency impact).

**Input Guard (`on_user_turn_completed` hook):**
- Classifies transcribed utterance into: `safe` / `off_topic` / `sensitive` / `distress`.
- `safe` → pass to LLM normally.
- `off_topic` → inject redirect instruction instead of raw transcript.
- `sensitive` → return canned response, skip LLM entirely.
- `distress` → distress protocol (see below). Latency: ~100–200ms added to turn.

**Output Guard (pre-TTS hook):**
- Regex and rule checks on LLM response text: no URLs, no domain names, no requests for personal info, no violent/scary framing phrases, length cap (600 chars). Fail → substitute canned response. No network call.

**Distress Protocol:**
- Fixed, non-improvised response encouraging the child to talk to a trusted adult.
- Fires on keywords/phrases indicating a child may be hurt, scared, or unsafe.
- Logs event to metrics (counter increment only — no content).

**Key decisions:** No off-the-shelf children's content classifier exists; Claude Haiku is the fastest available option for nuanced classification. The output guard is rule-only (no LLM) so it adds zero latency. Canned responses are pre-written by a human, not generated.

### Avatar Adapter — `avatar.py`
- **Purpose:** Thin abstraction over two avatar rendering strategies. Selected by environment variable at deploy time; swappable without touching any other module.
- **Technology:** Abstract base class `AvatarAdapter` with `start()`, `publish_audio()`, `stop()` methods. Two concrete implementations:
  - `LemonSliceAdapter`: wraps `livekit-plugins-lemonslice==1.5.12`. Publishes avatar video track to room. Startup sequence: `AgentSession` created → `avatar.start(session, room)` → `await avatar.wait_for_join()` → session started with `audio_enabled=False` (avatar republishes TTS audio synced to video).
  - `FrontendVisemeAdapter`: streams viseme/phoneme timing messages over a LiveKit data channel to the browser, where Three.js drives lip-sync locally. No external avatar vendor.
- **Inputs:** TTS audio chunks from Cartesia.
- **Outputs:** Option A — video + audio track in LiveKit room. Option B — data channel messages to browser.
- **Key decisions:** Phase 0 is an explicit bake-off measuring LemonSlice's real-world p50/p95 latency vs the 1.2s budget. If LemonSlice cannot meet latency, or quality is poor, `FrontendVisemeAdapter` is the default going forward (also removes the avatar per-minute cost and eliminates child audio/video ingestion by an external vendor).

### Observability / Metrics
- **Purpose:** Per-stage latency tracking, error rates, safety-trigger counts. No conversation content in any log or metric.
- **Technology:** `loguru` for structured logging. Prometheus counters/histograms exposed from the agent worker. Metrics collected per session: STT latency, input-guard latency, LLM TTFT, output-guard pass/fail counts, TTS first-chunk latency, total end-to-end utterance latency, session duration, guard trigger counts (by category).
- **Key decisions:** COPPA compliance requires that no audio, transcript text, or PII appear in any log line. Logging is metrics-only. `loguru` is configured with a sanitizing filter that strips any string matching transcript patterns before emission.

---

## 3. Data Flow — One Conversation Turn

**Happy path:**

1. Child presses PTT button → browser begins capturing mic audio.
2. Browser publishes audio track to LiveKit room (TURN relay if needed).
3. LiveKit SFU forwards audio to agent worker's subscribed audio track.
4. `DeepgramSTT` (Flux, `flux-general-en`) streams transcription. Native end-of-turn signal fires at utterance boundary (~0.8–1.0s patience).
5. `on_user_turn_completed` fires with completed transcript.
6. **Input guard** (`safety.py`): Claude Haiku classifies utterance (~150ms). Result: `safe`.
7. Transcript (or redirect instruction) injected into `AgentSession` LLM turn.
8. Claude Sonnet 4.6 generates response. Prompt cache hit on system prompt (1-hr TTL). First token arrives ~100–250ms.
9. Response text streamed to **output guard** (pre-TTS): rule checks pass.
10. Validated text chunks forwarded to Cartesia Sonic-3.5 over persistent WebSocket. First audio chunk returns ~188ms after first text chunk.
11. Audio chunk sent to `AvatarAdapter`. Option A: LemonSlice synthesizes lip-sync video and publishes to room. Option B: viseme timing messages sent to browser; Three.js animates locally.
12. Browser receives and plays avatar audio/video.

**Guard failure path (input guard — sensitive):**

Steps 1–6 as above. Input guard returns `sensitive`. Steps 7–11 are skipped. Safety module emits canned response text directly to output guard (passes) → Cartesia TTS → avatar. LLM is never called. Guard trigger counter incremented.

**Barge-in path:**

While avatar is playing audio (steps 11–12), if child holds PTT and speaks, `min_words=3` barge-in threshold is monitored. On threshold breach: current TTS playback is cancelled, avatar stops speaking, pipeline resets to step 3 with new utterance.

---

## 4. External Dependencies

| Service | Purpose | Auth Method | Failure Mode |
|---|---|---|---|
| LiveKit Cloud (Ship plan) | WebRTC SFU, room management | `LIVEKIT_API_KEY` + `LIVEKIT_API_SECRET` (server-side only) | Room join fails → frontend shows retry UI; agent worker reconnects with exponential backoff |
| Anthropic API (Claude Sonnet 4.6) | LLM turns + input guard (Haiku) | `ANTHROPIC_API_KEY` (agent worker env) | LLM timeout → canned "let me think" response after 3s; retry once |
| Deepgram Flux | STT + native end-of-turn | `DEEPGRAM_API_KEY` (agent worker env) | STT disconnect → LiveKit VAD fallback; alert on repeated failures |
| Cartesia Sonic-3.5 | TTS over persistent WebSocket | `CARTESIA_API_KEY` (agent worker env) | WS disconnect → reconnect on next turn; if 3 consecutive failures, session ends gracefully |
| LemonSlice (Option A only) | Avatar video rendering | `LEMONSLICE_API_KEY` (agent worker env) | Avatar timeout → session continues audio-only with frontend fallback state |
| Vercel (Next.js hosting) | Web frontend + token API | Vercel project env vars | Token API down → browser cannot join; surface error to parent |
| Fly.io | Agent worker hosting | Fly deploy token (CI only) | Worker crash → LiveKit disconnects session; auto-restart by Fly machine |

---

## 5. Environment Variables

**Agent worker** (`agent/.env` / Fly.io secrets):

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL (e.g., `wss://project.livekit.cloud`) |
| `LIVEKIT_API_KEY` | LiveKit API key for agent worker authentication |
| `LIVEKIT_API_SECRET` | LiveKit API secret — never in client code |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Sonnet 4.6 and Haiku |
| `DEEPGRAM_API_KEY` | Deepgram API key for Flux STT |
| `CARTESIA_API_KEY` | Cartesia API key for Sonic-3.5 TTS |
| `LEMONSLICE_API_KEY` | LemonSlice avatar API key (required only if `AVATAR_BACKEND=lemonslice`) |
| `AVATAR_BACKEND` | `lemonslice` or `frontend_viseme` — selects `AvatarAdapter` implementation |
| `MAX_SESSION_MINUTES` | Session hard cap (default: `15`). Agent signs off and disconnects at TTL. |
| `GUARD_LOG_TRIGGERS` | `true`/`false` — whether to log guard trigger category (never logs content) |

**Web / token API** (Vercel env vars):

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | Same LiveKit Cloud URL (needed for token minting) |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret — server-side Vercel env only, not `NEXT_PUBLIC_` |
| `SESSION_TOKEN_TTL_SECONDS` | Token TTL in seconds (default: `MAX_SESSION_MINUTES * 60 + 120`) |

---

## 6. Scaling Considerations

**What breaks first under load:**

1. **LiveKit Cloud concurrency (Ship plan: 5 concurrent agents).** Upgrade to Growth before soft launch. Growth supports ~50 concurrent rooms; Enterprise for beyond that. The hard session cap and per-day cost cap (configured in `MAX_SESSION_MINUTES` + application-layer rate limiting) bound runaway concurrency.

2. **LemonSlice concurrent sessions.** No published concurrency limit; treat as unknown until Phase 0 load test. If limits are hit, `AVATAR_BACKEND=frontend_viseme` removes this constraint entirely.

3. **Deepgram Flux: 150 streams on PAYG.** Upgrade to Growth for higher concurrency. Shared limit across all Deepgram usage on the account.

4. **Cost per session.** At ~$0.165/min with LemonSlice, a 15-min session costs ~$2.48. With `frontend_viseme`, cost drops to ~$0.75/session (avatar line eliminated). Per-day spend cap should be enforced at the application layer (counter in Redis or Fly.io KV) — stop accepting new sessions once daily budget is hit.

5. **Fly.io agent worker autoscaling.** `fly.toml` should configure `min_machines_running = 1` (eliminates cold starts) and `auto_stop_machines = false` during prod hours. Scale horizontally: each Fly machine handles one agent worker process. Fly's `concurrency` limit per machine should be `1` for this architecture (one session = one worker). Co-locate machines in the same region as the LiveKit Cloud cluster to minimize SFU-to-agent RTT.

6. **Latency budget risk — LemonSlice.** The published spec is "<3s" which does not satisfy the ≤1.2s p50 target. This is the single highest-risk unknown. Phase 0 must instrument per-stage latency. If LemonSlice p50 exceeds ~400ms (avatar-only contribution), the budget is blown and `frontend_viseme` becomes mandatory.

---

## 7. Key Architecture Decisions

**ADR-1: Swappable avatar behind `AvatarAdapter` abstraction.**  
The avatar vendor decision is unresolved at design time (Phase 0 bake-off). All downstream code (main.py, safety.py, persona.py) is decoupled from avatar implementation. Switching from LemonSlice to frontend Three.js, or to any future LiveKit-native avatar plugin, requires changing one environment variable and the concrete adapter class only.

**ADR-2: No-retention / COPPA architecture.**  
No audio recordings are stored. No transcripts are persisted. No conversation content appears in any log. STT audio is streamed in-memory and discarded. Deepgram `mip_opt_out=true` on every request. Anthropic ZDR arrangement. Cartesia DPA audit required before Phase 2 gate. Room names are UUIDs with no user linkage. Session tokens carry no identity. This is the only viable approach for a children's product without verifiable parental consent infrastructure.

**ADR-3: Push-to-talk over open mic.**  
Mic is active only while the PTT button is held. Rationale: (a) COPPA — minimizes ambient audio capture; (b) background-noise robustness on iPad in noisy environments (kids' bedrooms, classrooms); (c) clear interaction model for ages 5–10 who do not know conversational AI conventions. Trade-off: latency advantage of open-mic VAD is sacrificed, but the safety and UX gains dominate.

**ADR-4: Canned responses for sensitive topics; no LLM freeform on classified input.**  
When the input guard classifies an utterance as `sensitive` or `distress`, the LLM is never invoked. A human-authored canned response is used. This is a hard architectural rule. LLM improvisation on sensitive children's topics is unacceptable regardless of prompt quality.

**ADR-5: Kid-tuned turn-taking parameters.**  
Default LiveKit/Deepgram end-of-turn parameters are tuned for adult speech. Children ages 5–10 pause mid-sentence routinely at >800ms. Using Deepgram Flux's native end-of-turn (not LiveKit Turn Detector v1.0 separately — verify no double-firing in Phase 0) with an effective patience target of 0.8–1.0s. Barge-in requires `min_words=3` to avoid triggering on single-word exclamations. `false_interruption_timeout` set to ~1.2s.

**ADR-6: TURN-forced ICE for school and home networks.**  
`iceTransportPolicy: "relay"` is set unconditionally in the LiveKit client config. UDP is blocked on an estimated 15–20% of school networks; iCloud Private Relay on iPadOS interferes with WebRTC peer discovery. Forcing TURN relay eliminates these failure modes at the cost of slightly higher latency (acceptable within budget) and increased LiveKit Cloud egress.

**ADR-7: ElevenLabs for voice design only; Cartesia for production TTS.**  
ElevenLabs ToS prohibits under-18 users and submission of children's voice data — risk is unacceptable for production serving. Commander Sky's voice is designed in ElevenLabs Voice Design, then ported to Cartesia via voice clone (10s reference audio sufficient). Cartesia Sonic-3.5 serves all production TTS. ElevenLabs dependency is build-time only, not runtime.

**ADR-8: Bake-off result — LemonSlice is the production avatar (decided 2026-07-17).**  
Live measurement, 8-turn conversation, `AVATAR_MODE=lemonslice`: utterance-end → first TTS audio p50 ≈ 1.19s, max ≈ 2.64s (cache-cold first turn). Stage breakdown: Flux end-of-turn 2ms, LLM TTFT p50 1,098ms (the bottleneck), Cartesia TTFB p50 101ms. A/B against `AVATAR_MODE=none`: no perceptible latency difference reported — the avatar renders in parallel with audio and is off the critical path. Decision: keep LemonSlice; the frontend-Three.js path (Option B) remains the documented fallback for cost or vendor-risk reasons, not latency. Caveats: avatar first-frame time not yet instrumented. Follow-up (same day): guard instrumented — p50 642ms serial per turn, max 1.25s; Flux eager EOT (0.6) + preemptive TTS enabled, overlapping guard/LLM work with the utterance tail — owner reports perceived latency now good. Next lever if ever needed: speculative guard/LLM overlap (~0.6s further). Note: Haiku 4.5 persona swap was tested and showed no TTFT improvement (p50 1,156ms) — latency is per-call overhead, not model speed; Sonnet 4.6 retained.

**ADR-9 (supersedes ADR-3 and ADR-5 in part): General-audience pivot (owner decision 2026-07-17).**  
Product audience changed from children 5–10 to general public, and the default mic posture changed from push-to-talk to auto-connect + always-on mic with mute toggle (`NEXT_PUBLIC_MIC_MODE=ptt` restores PTT). Turn-taking retuned to 0.5s endpointing. Safety architecture retained with adult calibration. COPPA analysis must be revisited by counsel: the character may still be "attractive to children" under FTC factors (see docs/compliance.md).
