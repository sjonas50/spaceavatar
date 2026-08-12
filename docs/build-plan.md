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

---

# Upgrade Plan (2026-08-12): Latency · Knowledge · Polish

Phases 0–5 shipped and deployed (Vercel + Fly, Anam CARA-4 avatar). This plan
takes the live product further. Same rule: **a phase is complete only when its
gate passes.**

**Measured baseline (prod session, 2026-08-12):** endpointing 0.5s (prod
default) · input guard up to **1,337ms even on a speculative hit** · LLM TTFT
**~1.49s** · Cartesia TTFB 117–494ms · avatar join 1.1–4.2s. Per-turn serial
latency (utterance-end → first audio) ≈ **2.5–3.5s**. Target: **≤1.5s p50,
≤2.5s p95**.

The serial reply path is `eou_delay → guard → LLM TTFT → TTS TTFB → avatar`.
The two fat targets are the guard (should be ~0 on speculative hits) and LLM
TTFT (should be ~0.6–0.9s with a warm prompt cache).

## Phase U0 — Turn-Latency Instrumentation (S)

Can't cut what we can't see per-turn.

| # | Task | Files |
|---|---|---|
| U0.1 | `TurnLatency` aggregator: per turn, sum `end_of_utterance_delay` (EOUMetrics) + `guard_ms` + LLM `ttft` + TTS `ttfb`; emit `turn_latency` log line per turn and p50/p95 in the final session snapshot. Content-free as ever. | `metrics.py`, `main.py`, `tests/test_no_content_logging.py` |
| U0.2 | Baseline capture: scripted 6-turn local session (Playwright fake-mic driver from scratchpad → `web/e2e/latency-probe.ts`), record the table | `docs/latency-baseline.md` |

**Gate:** `uv run pytest` + committed baseline table.

## Phase U1 — Serial-Path Latency Cuts (M)

| # | Task | Files |
|---|---|---|
| U1.1 | Guard prompt caching: `cache_control: ephemeral` on the classifier system prompt (it's static), cap `max_tokens` at the one-word answer; log guard cache hits | `safety.py` |
| U1.2 | Speculation coverage: start speculation on the *first* interim transcript (current throttle waits too long — prod showed 1.3s awaits on "hits"); log `speculation_ready` vs `awaited_ms`; drop `guard_timeout_s` default 2.5→1.5 (fail-closed unchanged) | `safety.py`, `sky_agent.py`, `config.py` |
| U1.3 | LLM cache observability: log `cache_read_input_tokens` / `cache_creation_input_tokens` per turn; a cache-miss streak means the prefix is unstable — find and fix | `metrics.py` |
| U1.4 | Prompt diet: count persona+facts tokens (prod first turn showed ~20k prompt tokens); move any fact not needed for instant recall into the archive corpus; target < 8k. Smaller prefix = faster TTFT even on cache hits | `persona.py`, `facts/*.md`, `knowledge/` |
| U1.5 | Sync local `.env` endpointing 0.9→0.5 to match prod; verify preemptive generation actually fires (log when eager EOT wins the race) | `.env`, `main.py` |

**Gate:** `uv run pytest` + dry-run + measured on the U0.2 probe: guard p50 <150ms, speculative-hit rate >80%, turn e2e p50 ≤1.5s.

## Phase U2 — Knowledge Expansion (M)

Same pattern as `satellites_earth_tech.md`: curated, dated, review-header,
heading-level chunks, retrieval tests per file.

| # | Task | Files |
|---|---|---|
| U2.1 | `mars_exploration.md` — rovers Sojourner→Perseverance, Ingenuity, why Mars, water evidence, sample return status (dated) | `knowledge/` |
| U2.2 | `telescopes_discoveries.md` — Hubble/JWST deep dives, exoplanets & transit method, gravitational waves/LIGO, famous images | `knowledge/` |
| U2.3 | `comets_asteroids_meteors.md` — belt/Kuiper/Oort, dinosaur impact, DART planetary defense, meteor showers, Bennu/OSIRIS-REx | `knowledge/` |
| U2.4 | `space_agencies_programs.md` — NASA/ESA/JAXA/ISRO/CNSA highlights, international cooperation, commercial space (SpaceX/Blue Origin/Rocket Lab) | `knowledge/` |
| U2.5 | `artemis_moon_future.md` — Artemis status (dated as of mid-2026), Gateway, lunar south pole & water ice, Mars ambitions | `knowledge/` |
| U2.6 | Keyterm expansion for STT biasing: satellite, GPS, Mars, rover, telescope, Artemis, SpaceX, Starlink, black hole, comet, asteroid | `main.py` `SPACE_KEYTERMS` |
| U2.7 | Recall sweep: ≥25 parametrized retrieval queries across all 13 corpus files; if any file's recall disappoints, record the BM25→embeddings swap decision in `docs/architecture.md` | `tests/test_knowledge.py` |

**Gate:** `uv run pytest tests/test_knowledge.py tests/test_pipeline.py -v`

## Phase U3 — Quality Gates & Resilience E2E (M)

| # | Task | Files |
|---|---|---|
| U3.1 | Extend `persona_script.yaml` with satellite/Mars/telescope questions; run the live 30+ question LLM-judge gate (`RUN_PERSONA_SCRIPT=1`, real keys) | `tests/persona_script.yaml` |
| U3.2 | Playwright e2e: avatar-death fallback (voice continues + in-character line) and 90s idle shutdown | `web/e2e/` |
| U3.3 | Guard red-team additions for the new scope (e.g. "spy satellites on my neighbor" → still guarded; "how do I jam GPS" → sensitive) | `tests/test_safety.py` |

**Gate:** live persona script pass + `npx playwright test` + `uv run pytest tests/test_safety.py -v`

## Phase U4 — Ops Polish (S)

| # | Task | Files |
|---|---|---|
| U4.1 | Latency SLO: warn-level log when a turn's e2e exceeds 2.5s (`turn_latency_slo_breach`) so slow turns are greppable in Fly logs | `metrics.py` |
| U4.2 | Scale checklist: Anam tier upgrade steps, concurrency math (Anam concurrent cap vs LiveKit participant minutes vs Fly machine count) | `docs/deploy.md` |

**Gate:** `uv run pytest` + updated docs.

## Sequence & Complexity

| Phase | Complexity | Depends on |
|---|---|---|
| U0 Instrumentation | S | — |
| U1 Latency cuts | M | U0 (need the numbers) |
| U2 Knowledge | M | — (parallel with U0/U1) |
| U3 Quality gates | M | U1, U2 |
| U4 Ops polish | S | U1 |

~19 tasks. U2 is independent — it can interleave with the latency work.
Out of scope (recorded, not planned): frontend-rendered avatar (strategic
end-state per research addendum), embeddings retrieval (only if U2.7 shows
BM25 recall gaps), LLM model swap (Sonnet stays — persona quality is the
product).
