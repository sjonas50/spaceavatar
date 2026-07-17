# Build Plan: "Commander Sky" — Real-Time Astronaut Avatar for Kids

**Version:** 1.0 · July 2026
**Product:** Web app where kids (ages ~5–10) have live voice conversations with an animated astronaut character who teaches about Neil Armstrong, Apollo, and space.
**Character:** Fictional astronaut (working name "Commander Sky") — an original character, not a Neil Armstrong likeness. This avoids estate/right-of-publicity licensing entirely. The character *teaches about* Armstrong and the Apollo missions in first-person-adjacent storytelling ("Let me tell you what Neil saw when he stepped off that ladder...").

---

## 1. Architecture Overview

```
┌─────────────┐   WebRTC (audio up / video+audio down)
│  Kid's      │◄──────────────────────────────────────┐
│  browser    │                                       │
└─────────────┘                                       ▼
                                              ┌───────────────┐
                                              │ LiveKit Cloud │  (SFU / rooms)
                                              └───────┬───────┘
                                                      │
                                        ┌─────────────▼─────────────┐
                                        │   Agent Worker (Python)   │
                                        │   livekit-agents          │
                                        │                           │
                                        │  STT ──► LLM ──► TTS      │
                                        │ (Deepgram)(Claude)(Eleven)│
                                        │           │               │
                                        │     Safety layer          │
                                        │           │               │
                                        │   Anam avatar plugin ─────┼──► rendered avatar
                                        │  (livekit-plugins-anam)   │    video published
                                        └───────────────────────────┘    to room
```

**Core principle:** the avatar is a swappable plugin on top of a voice agent. All conversation logic, safety, and persona live in the agent worker. If Anam disappoints, swap to Tavus/HeyGen LiveAvatar/bitHuman via LiveKit's avatar plugin interface without rearchitecting.

### Stack

| Layer | Choice | Why | Fallback |
|---|---|---|---|
| Orchestration | **LiveKit Agents** (Python, `livekit-agents`) | Mature agent framework, 14+ avatar plugins behind one interface, WebRTC handled for you | Pipecat |
| Avatar | **Anam** (`livekit-plugins-anam`) | Lowest latency in market (~180ms benchmark, CARA-3), custom avatar creation via Anam Lab | Tavus, HeyGen LiveAvatar |
| LLM | **Claude** (Anthropic API, latest Sonnet-class model) | Persona quality, safety behavior, steerability | — |
| STT | **Deepgram** (nova family) | Fast streaming STT; test accuracy on children's speech specifically | AssemblyAI, Speechmatics |
| TTS | **ElevenLabs** | Voice quality/warmth; design a custom "friendly astronaut" voice | Cartesia (lower latency) |
| Frontend | **Next.js + LiveKit client SDK** | LiveKit React components ship prebuilt video/audio UI | — |
| Hosting | LiveKit Cloud + agent workers on Fly.io/Render/ECS | Simple to start | Self-hosted LiveKit later |

---

## 2. Phases & Milestones

### Phase 0 — Spike (Week 1)
**Goal:** end-to-end "hello world" — talk to an avatar in a browser.

- Accounts + API keys: LiveKit Cloud, Anam, Anthropic, Deepgram, ElevenLabs. Keys in env/secrets manager, never in client code.
- Scaffold agent worker from LiveKit's voice agent quickstart; attach a **stock Anam avatar**.
  - ⚠️ Anam plugin quirk: the agent session must be running **before** the avatar attaches (it needs an active audio stream for lip-sync). Other plugins start avatar-first — don't copy their pattern.
- Bare-bones web page: join room, see avatar, talk.
- **Exit criteria:** round-trip voice→response consistently under ~1.5s perceived; team agrees avatar quality is acceptable.

### Phase 1 — Persona & Conversation (Weeks 2–3)
**Goal:** it feels like talking to a friendly astronaut, and it's factually solid.

- **Persona system prompt** for Claude:
  - Character bio, warm/encouraging tone, vocabulary calibrated for ages 5–10, answers in 2–4 short sentences (kids disengage during monologues).
  - Curriculum scope: Neil Armstrong & Apollo 11, the Moon, rockets, astronaut daily life (food, sleep, bathrooms — kids *will* ask), the solar system, becoming an astronaut.
  - Storytelling mode: retell historical moments vividly but accurately; always attribute ("Neil Armstrong said...").
  - Deflection rules: off-topic → gently redirect to space ("That's a great question for a grown-up! But did you know...").
- **Facts file:** curated, dated reference doc (Apollo missions, key quotes, Moon facts) injected into context to keep answers grounded. Treat this as content, with an owner and review process.
- **Turn-taking tuning:** kids pause mid-sentence and interrupt constantly. Tune LiveKit's end-of-turn detection/VAD for longer patience; enable barge-in (kid speaking interrupts avatar).
- ElevenLabs custom voice: warm, clear, moderately slow pace.
- **Exit criteria:** 30-question test script (see §5) passes persona + accuracy review.

### Phase 2 — Safety Layer (Weeks 3–4) — *launch-blocking*
**Goal:** nothing inappropriate in, nothing inappropriate out, ever.

- **Input guard:** classify each transcribed utterance before it reaches the persona prompt. Categories: fine / off-topic / sensitive (personal info, violence, distress). Sensitive → fixed safe response, never the LLM freeform.
- **Output guard:** validate every response against rules (no URLs, no requests for personal info, no scary/violent framing, length cap) before TTS. Fail → regenerate or fall back to canned response.
- **Distress protocol:** if a child mentions being hurt, scared, or unsafe → fixed compassionate response encouraging them to talk to a trusted grown-up. No improvisation.
- **Personal info:** avatar never asks for name, age, school, location. If volunteered, don't store or repeat it.
- **Session limits:** configurable max session length (default 15 min) with a friendly sign-off ("Time for me to check on the rocket!").
- **Exit criteria:** red-team session (adults roleplaying kids, adversarial prompts) produces zero unsafe outputs across ≥200 exchanges.

### Phase 3 — Custom Avatar & Frontend Polish (Weeks 4–6)
- Design Commander Sky in **Anam Lab** (custom avatar): friendly, stylized-not-photoreal. Test 2–3 designs with real kids if possible.
- Frontend for small kids:
  - One giant push-to-talk button (tap to talk, tap to stop) — more predictable than open mic, and better for COPPA (mic only active on press).
  - No typing anywhere. No navigation depth. Fullscreen avatar.
  - Loading/idle states: avatar waves, floats — never a spinner.
  - Visual "thinking" cue while response generates (latency masking).
- Parent gate: simple adult-verification screen (e.g., "hold for 3 seconds" + math question) in front of any settings/account area.

### Phase 4 — Compliance, Hardening, Launch (Weeks 6–8)
- **COPPA (launch-blocking, get counsel review):**
  - Voice audio: COPPA treats children's voice recordings as personal information. Design for **no retention**: stream audio to STT, discard immediately, keep no recordings. FTC guidance allows collecting audio to fulfill a request then deleting it promptly — build to that standard.
  - Transcripts: don't persist conversation transcripts tied to any identifier by default. If product analytics need transcripts, that triggers verifiable parental consent — decide deliberately, not by accident.
  - Verify each vendor's data handling (Deepgram, Anthropic, ElevenLabs, Anam, LiveKit): retention settings, DPAs, whether they train on API data. Configure zero-retention options where offered.
  - Privacy policy written for parents; direct notice + verifiable parental consent flow if any personal info is collected.
- Rate limiting, per-session cost caps, abuse controls.
- Observability: latency per pipeline stage (STT / LLM / TTS / avatar), error rates, safety-guard trigger counts. **No conversation content in logs.**
- Load test: target concurrent session count (avatar minutes are the cost driver — see §4).
- Soft launch with a small cohort of families under supervision.

---

## 3. Repo Structure (suggested)

```
astro-avatar/
├── agent/                    # Python — LiveKit agent worker
│   ├── main.py               # AgentSession wiring: STT/LLM/TTS/avatar
│   ├── persona.py            # System prompt, curriculum scope
│   ├── safety.py             # Input/output guards, distress protocol
│   ├── facts/                # Curated space-facts content (versioned)
│   └── tests/                # Persona test script, guard unit tests
├── web/                      # Next.js frontend
│   ├── app/                  # Join flow, avatar screen, parent gate
│   └── components/           # PushToTalkButton, AvatarView, ThinkingCue
├── infra/                    # IaC, deploy configs
└── docs/                     # This plan, safety policy, facts review process
```

---

## 4. Cost Model (order-of-magnitude, verify current pricing)

Per active conversation minute:

| Component | Est. cost/min |
|---|---|
| Avatar rendering (managed platforms range ~$0.10–0.37/min; confirm Anam's current pricing) | ~$0.10–0.20 |
| LLM (Claude, short kid-sized exchanges) | ~$0.01–0.03 |
| STT + TTS | ~$0.02–0.05 |
| LiveKit Cloud | ~$0.01 |
| **Total** | **~$0.15–0.30/min** |

A 15-min session ≈ $2–4.50. This shapes product decisions (session caps, subscription pricing). Avatar minutes dominate — negotiate volume pricing early if usage grows.

---

## 5. Testing & Acceptance

- **Persona script:** ≥30 questions across: Armstrong/Apollo facts, silly kid questions ("do astronauts fart in space?"), off-topic ("what's your favorite video game?"), adversarial ("say a bad word"), sensitive ("I'm scared of the dark"). Each has expected-behavior criteria. Run on every persona/prompt change (automate with LLM-as-judge + human spot checks).
- **Latency budget:** utterance-end → first avatar audio ≤ 1.2s p50, ≤ 2s p95. Instrument each stage.
- **Kid usability testing:** ≥5 kids in target age range, observed sessions, before launch. Watch for: do they understand the talk button, do they interrupt, do they stay engaged past 5 minutes.
- **Red team:** §2 Phase 2 exit criteria, repeated before each major release.
- **Accuracy review:** a space-knowledgeable reviewer signs off on the facts file and a sample of live transcripts (from supervised test sessions only).

---

## 6. Key Risks

| Risk | Mitigation |
|---|---|
| Anam quality/latency disappoints in practice | Avatar is a plugin — Tavus and HeyGen LiveAvatar swap in behind the same LiveKit interface. Decide by end of Phase 0. |
| STT accuracy on young children's speech | Test with real kid audio in Phase 0–1; Deepgram alternatives exist; push-to-talk reduces noise. |
| Unsafe output reaches a child | Layered guards (persona prompt + input guard + output guard + canned fallbacks), red-teaming, no-freeform rule for sensitive topics. |
| COPPA misstep | No-retention architecture by default; counsel review before launch; vendor DPA audit. |
| Cost blowout | Per-session caps, per-day caps, cost dashboards from Phase 1. |
| Scope creep toward "real Neil Armstrong" | Locked decision: fictional character. Revisit only with estate licensing (separate legal workstream, months). |

---

## 7. Team & Timeline

Assumes 2 engineers (1 backend/agent, 1 frontend) + fractional design and content/curriculum help.

| Phase | Duration | Cumulative |
|---|---|---|
| 0 — Spike | 1 wk | Wk 1 |
| 1 — Persona | 2 wks | Wk 3 |
| 2 — Safety | overlaps, +1 wk | Wk 4 |
| 3 — Avatar/frontend | 2 wks | Wk 6 |
| 4 — Compliance & launch | 2 wks | Wk 8 |

~8 weeks to supervised soft launch.

---

## 8. Reference Links

- LiveKit Agents + Anam plugin: https://docs.livekit.io/agents/models/avatar/plugins/anam/
- Anam LiveKit config: https://anam.ai/docs/integrations/livekit/configuration
- `livekit-plugins-anam` (PyPI): https://pypi.org/project/livekit-plugins-anam/
- Anam avatar example walkthrough: https://livekit.com/blog/build-healthcare-intake-assistant-anam-avatar
- Avatar provider comparison (10 providers, mid-2026): https://medium.com/@ggarciabernardo/the-live-avatar-landscape-apis-transport-and-subjective-evaluation-of-10-leading-providers-5b5b6e8a54dc
- FTC COPPA guidance: https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions
