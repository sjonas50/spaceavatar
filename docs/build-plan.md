# Engineering Build Plan: Commander Sky

**Inputs:** `BUILD_PLAN.md` (product plan) · `docs/research.md` (stack decisions) · `docs/architecture.md` (system design)
**Rule:** a phase is complete only when its **gate command passes**. Do not advance on a red gate.

---

## Phase 0 — Scaffold (S)

Project skeleton, tooling, config plumbing. No product logic.

| # | Task | Files |
|---|---|---|
| 0.1 | Python agent scaffold: `uv init` src-layout, pin `livekit-agents~=1.6`, plugins (`deepgram`, `anthropic`, `cartesia`, `lemonslice`), `pydantic-settings`, dev deps `ruff`, `pytest`, `pytest-asyncio` | `agent/pyproject.toml`, `agent/src/commander_sky/__init__.py` |
| 0.2 | Typed env config with pydantic-settings: all keys from `docs/architecture.md` §5 (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `LEMONSLICE_API_KEY`, `AVATAR_MODE`, `MAX_SESSION_MINUTES`) | `agent/src/commander_sky/config.py`, `.env.example` |
| 0.3 | Test + lint harness: conftest with settings fixture (fake keys), smoke test importing `commander_sky`, ruff config (format + lint) | `agent/tests/conftest.py`, `agent/tests/test_smoke.py` |
| 0.4 | Next.js scaffold (App Router, TypeScript) with `livekit-client` + `@livekit/components-react`; placeholder home page | `web/` (create-next-app), `web/package.json` |

**Gate:**
```bash
cd agent && uv run ruff check . && uv run pytest && cd ../web && npm run lint && npm run build
```

---

## Phase 1 — Core Models, Persona & Facts (M)

Everything the pipeline consumes, testable without network.

| # | Task | Files |
|---|---|---|
| 1.1 | Pydantic schemas: `GuardVerdict` (category: fine/off_topic/sensitive/distress, action, canned_response_id), `TurnMetrics` (per-stage latency), `SessionLimits` | `agent/src/commander_sky/models.py` |
| 1.2 | Facts content: curated, dated Apollo/Armstrong/Moon facts file + loader that injects into system prompt | `agent/src/commander_sky/facts/apollo.md`, `facts/loader.py` |
| 1.3 | Persona builder: `build_system_prompt(facts: str) -> str` — character bio, ages 5–10 vocabulary, 2–4 sentence answers, attribution rules, deflection rules (per product plan §Phase 1) | `agent/src/commander_sky/persona.py` |
| 1.4 | Unit tests: schema validation edge cases (parametrized), persona prompt contains required rules, facts loader handles missing/malformed files | `agent/tests/test_models.py`, `test_persona.py`, `test_facts.py` |

**Gate:**
```bash
cd agent && uv run ruff check . && uv run pytest tests/ -v
```

---

## Phase 2 — Voice Pipeline + Avatar Bake-off (L)

End-to-end "talk to Commander Sky in a browser." This is the product plan's Phase 0 spike — includes the **LemonSlice vs frontend-render decision**.

| # | Task | Files |
|---|---|---|
| 2.1 | Agent worker entrypoint: `AgentSession` wiring — Deepgram Flux (`flux-general-en`, keyterm biasing with space vocab, `mip_opt_out=true`), Claude Sonnet 4.6 (prompt caching), Cartesia Sonic-3.5. Kid-tuned turn-taking: endpointing delay 0.8–1.0s, `min_words=3` barge-in. Follow canonical avatar startup order (avatar.start → wait_for_join → session.start, `audio_enabled=False`) | `agent/src/commander_sky/main.py` |
| 2.2 | Avatar adapter: `AVATAR_MODE=lemonslice \| frontend \| none` — LemonSlice `AvatarSession` behind an interface; `frontend` mode publishes audio only | `agent/src/commander_sky/avatar.py` |
| 2.3 | Token API: Next.js route handler minting LiveKit access tokens (room grant, TTL = `MAX_SESSION_MINUTES`); server-side secrets only | `web/app/api/token/route.ts` |
| 2.4 | Minimal join page: connect to room, render avatar video track (or audio + placeholder), push-to-talk mic publish | `web/app/session/page.tsx`, `web/components/PushToTalkButton.tsx` |
| 2.5 | Latency instrumentation: per-stage timers (STT/LLM/TTS/avatar first-frame) logged as metrics — **no conversation content in logs** | `agent/src/commander_sky/metrics.py` |
| 2.6 | **Bake-off (decision task):** measure utterance-end → first audio p50/p95 with LemonSlice vs audio-only; record decision + numbers in `docs/architecture.md` ADR section | `docs/architecture.md` update |

**Gate:**
```bash
cd agent && uv run pytest tests/ && uv run python -m commander_sky.main dev --dry-run
```
**Manual exit criteria (from product plan):** round-trip ≤ ~1.5s perceived; avatar quality acceptable; bake-off decision recorded.

---

## Phase 3 — Safety Layer (M) — *launch-blocking*

| # | Task | Files |
|---|---|---|
| 3.1 | Input guard: `on_user_turn_completed` hook → sync Claude Haiku classification (fine/off_topic/sensitive/distress); sensitive/distress short-circuit to canned responses, never freeform LLM | `agent/src/commander_sky/safety.py` |
| 3.2 | Output guard: pre-TTS validation — no URLs, no PII requests, length cap, no scary/violent framing; fail → regenerate once, then canned fallback | `safety.py` |
| 3.3 | Canned responses + distress protocol: fixed compassionate "talk to a trusted grown-up" response; deflection lines for off-topic | `agent/src/commander_sky/canned.py` |
| 3.4 | Session limits: max session length with friendly sign-off; per-session cost cap | `main.py`, `config.py` |
| 3.5 | Guard test suite: parametrized adversarial cases (bad words, PII fishing, scary topics, distress phrases, jailbreak attempts) — input guard mocked-LLM unit tests + output guard pure-function tests | `agent/tests/test_safety.py`, `test_canned.py` |

**Gate:**
```bash
cd agent && uv run pytest tests/test_safety.py tests/test_canned.py -v --tb=short
```
**Manual exit criteria:** red-team session (product plan §Phase 2) — zero unsafe outputs across ≥200 exchanges.

---

## Phase 4 — Kid-Facing Frontend & Custom Avatar (M)

| # | Task | Files |
|---|---|---|
| 4.1 | Fullscreen avatar UI: no typing, no nav depth; idle/loading states (wave/float, never a spinner); visual "thinking" cue during generation | `web/app/session/page.tsx`, `web/components/AvatarView.tsx`, `ThinkingCue.tsx` |
| 4.2 | Push-to-talk polish: giant button, tap-to-talk/tap-to-stop, mic active only while engaged (COPPA); clear visual states | `web/components/PushToTalkButton.tsx` |
| 4.3 | Parent gate: hold-3-seconds + math question in front of settings | `web/app/parent/page.tsx`, `web/components/ParentGate.tsx` |
| 4.4 | Custom Commander Sky avatar: design stylized character (LemonSlice single-image, or Three.js model if frontend mode won bake-off); wire into avatar adapter | asset + `avatar.py` / `web/components/` |
| 4.5 | iPad Safari + school network hardening: TURN-forced ICE config, reconnect handling; test on iPadOS Safari | `web/lib/livekit.ts` |

**Gate:**
```bash
cd web && npm run lint && npm run build && npx playwright test
```
**Manual exit criteria:** kid usability test ≥5 kids (product plan §5) — scheduled, not blocking merge.

---

## Phase 5 — Hardening, Compliance & Launch Prep (L)

| # | Task | Files |
|---|---|---|
| 5.1 | Persona test script: ≥30 questions (facts/silly/off-topic/adversarial/sensitive) with expected-behavior criteria; LLM-as-judge runner, runs on every persona change | `agent/tests/persona_script.yaml`, `agent/tests/test_persona_script.py` |
| 5.2 | Observability: per-stage latency histograms, error rates, guard trigger counts; assert-no-content log filter with test | `metrics.py`, `agent/tests/test_no_content_logging.py` |
| 5.3 | Rate limiting + per-day cost caps + abuse controls on token API | `web/app/api/token/route.ts`, `web/lib/ratelimit.ts` |
| 5.4 | Deploy: agent Dockerfile + `fly.toml` (co-located with LiveKit region), Vercel config, secrets via Fly/Vercel env | `agent/Dockerfile`, `infra/fly.toml` |
| 5.5 | Compliance checklist doc: vendor DPA status, ZDR settings (Anthropic ZDR, Deepgram `mip_opt_out`, Cartesia retention audit, LemonSlice/ElevenLabs ToS confirmations), privacy policy draft for counsel | `docs/compliance.md` |

**Gate:**
```bash
cd agent && uv run ruff check . && uv run pytest && docker build -t commander-sky-agent . && cd ../web && npm run build
```
**Manual exit criteria:** counsel COPPA review; red-team repeat; load test at target concurrency; supervised soft launch.

---

## Complexity & Sequence

| Phase | Complexity | Depends on |
|---|---|---|
| 0 Scaffold | S | — |
| 1 Models/Persona | M | 0 |
| 2 Pipeline + bake-off | L | 1 |
| 3 Safety | M | 2 (can start with 2 in flight) |
| 4 Frontend/Avatar | M | 2 bake-off decision |
| 5 Hardening/Launch | L | 3, 4 |

~25 tasks total. Phases 3 and 4 can run in parallel (backend vs frontend engineer) once the Phase 2 bake-off decision lands.
