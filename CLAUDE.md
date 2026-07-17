# Commander Sky — Real-Time Astronaut Avatar for Kids

Web app where kids (ages 5–10) have live voice conversations with a stylized animated astronaut who teaches about Neil Armstrong, Apollo, and space. LiveKit Agents pipeline: Deepgram Flux STT → safety guards → Claude Sonnet 4.6 → Cartesia TTS → avatar (LemonSlice or frontend-rendered — Phase 2 bake-off decides).

## Key Documents

- `BUILD_PLAN.md` — product plan (phases, safety requirements, COPPA, cost model)
- `docs/research.md` — validated stack decisions with rationale (July 2026)
- `docs/architecture.md` — system design, data flow, env vars, ADRs
- `docs/build-plan.md` — engineering phases with test gates (source of truth for build order)

## Commands

```bash
# Agent (Python 3.12, uv, src layout)
cd agent
uv sync                          # install deps
uv run ruff check . --fix        # lint
uv run ruff format .             # format
uv run pytest                    # all tests
uv run pytest tests/test_safety.py -v   # safety gate
uv run python -m commander_sky.main dev # run agent worker locally

# Web (Next.js, TypeScript)
cd web
npm run dev                      # local dev server
npm run lint && npm run build    # gate
npx playwright test              # e2e
```

## Architecture Decisions (locked — don't relitigate)

- **Fictional character**, not Neil Armstrong likeness (no estate licensing). Teaches *about* Armstrong with attribution.
- **Avatar is swappable** behind `avatar.py` adapter (`AVATAR_MODE=lemonslice|frontend|none`). Anam is ruled out: photoreal-only, conflicts with stylized requirement.
- **No-retention COPPA architecture**: no audio persisted, no transcripts persisted, **no conversation content in any log line** — metrics only (latency, error rates, guard counts). Deepgram calls always set `mip_opt_out=true`.
- **Mic mode** — owner decision 2026-07-17: default is auto-connect + always-on
  open mic with mute toggle (`NEXT_PUBLIC_MIC_MODE=open`). Push-to-talk
  (`=ptt`) remains available and is the COPPA-preferred launch posture —
  flagged for counsel review in docs/compliance.md.
- **Sensitive/distress inputs never reach the freeform LLM** — canned responses only.
- **Kid-tuned turn-taking**: endpointing delay 0.8–1.0s (kids pause mid-thought), `min_words=3` barge-in.

## Stack-Specific Pitfalls (from research — read before touching the pipeline)

- **Avatar startup order**: `avatar.start(session, room)` → `await avatar.wait_for_join()` → `session.start(...)` with `RoomOutputOptions(audio_enabled=False)`. Wrong order = audio-before-video; missing `audio_enabled=False` = double audio.
- **Don't stack endpointing delays**: Deepgram Flux has native end-of-turn. If Flux controls timing, set LiveKit `min_delay=0` (livekit/agents #4325 — delays stack in STT mode).
- **`livekit-plugins-lemonslice` lags core** (1.5.x vs 1.6.x) — verify compatibility before bumping `livekit-agents`.
- **Cartesia**: use `sonic-3.5` (Sonic-2 EOL June 2026). Persistent WebSocket, not per-turn HTTP.
- **Claude prompt caching**: persona + facts prompt uses 1-hour cache (`cache_control`); keep the static prefix stable — edits invalidate the cache.
- **iPad Safari is a first-class target**: force TURN relay in ICE config (school networks block UDP); test reconnects.
- **Children's STT accuracy is 2–3× worse** than adult benchmarks across all vendors — use Flux keyterm biasing with space vocabulary; expect and handle garbled transcripts gracefully.
- **Secrets are server-side only** — LiveKit tokens minted in `web/app/api/token/route.ts`; no API key ever reaches the browser.

## File Structure

```
agent/src/commander_sky/
  main.py      # AgentSession wiring (STT/LLM/TTS/avatar)
  config.py    # pydantic-settings env config
  models.py    # GuardVerdict, TurnMetrics, SessionLimits
  persona.py   # system prompt builder
  safety.py    # input guard (Haiku classify), output guard (rules)
  canned.py    # fixed responses: distress, deflection, fallback
  avatar.py    # avatar adapter (lemonslice | frontend | none)
  metrics.py   # per-stage latency, no-content logging
  facts/       # curated space facts (versioned content)
agent/tests/   # incl. persona_script.yaml (30-question gate)
web/           # Next.js: token API, session UI, parent gate
infra/         # Dockerfile context, fly.toml
docs/          # research, architecture, build-plan, compliance
```

## Conventions

- Python 3.12, type hints everywhere, Google docstrings, ruff format+lint, pytest with parametrize.
- Pydantic models for all cross-boundary data (guard verdicts, metrics, config).
- Conventional commits (`feat:`, `fix:`, `test:`...).
- Safety code changes require running `uv run pytest tests/test_safety.py` before commit — this gate is launch-blocking.
