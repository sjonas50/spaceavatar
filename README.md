# Commander Sky 🧑‍🚀

Real-time voice conversations with an animated astronaut who teaches about Neil
Armstrong, Apollo, and space. Open the page, start talking — Commander Sky
greets you, answers with grounded facts, tells stories, and gestures while she
talks.

Built on a cascaded voice pipeline with a hard safety layer:

```
Browser ──WebRTC──► LiveKit Cloud ──► Agent worker (Python)
                                       │
                                       ▼
                        Deepgram Flux (STT + end-of-turn)
                                       │
                        Input guard (Claude Haiku, fail-closed)
                                       │
                        Claude Sonnet 4.6 (persona, prompt-cached)
                                       │
                        Output guard (deterministic rules)
                                       │
                        Cartesia Sonic-3.5 (TTS)
                                       │
                        LemonSlice avatar (synced video) ──► back to browser
```

## Stack

| Layer | Tech |
|---|---|
| Orchestration | [LiveKit Agents](https://docs.livekit.io/agents/) 1.6 (Python 3.12) |
| STT + turn detection | Deepgram Flux (`flux-general-en`, eager end-of-turn) |
| LLM | Claude Sonnet 4.6 (persona) + Claude Haiku 4.5 (input guard) |
| TTS | Cartesia Sonic-3.5 |
| Avatar | LemonSlice (swappable: `lemonslice` \| `frontend` \| `none`) |
| Frontend | Next.js 16 + LiveKit client SDK |

## Quickstart

Prereqs: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 20+, and
accounts/API keys for LiveKit Cloud, Anthropic, Deepgram, Cartesia, and
LemonSlice.

```bash
cp .env.example .env        # fill in your keys (never committed)

# Agent worker
cd agent
uv sync
uv run python -m commander_sky.main dry-run   # offline wiring check, no keys needed
uv run python -m commander_sky.main dev       # connect to LiveKit Cloud

# Web app (second terminal)
cd web
npm install
set -a && source ../.env && set +a && export NEXT_PUBLIC_ICE_POLICY=all
npm run dev                                   # open http://localhost:3000
```

The page auto-connects and the mic is always on by default
(`NEXT_PUBLIC_MIC_MODE=ptt` restores push-to-talk).

## Safety design

The persona prompt shapes behavior; the guards enforce it:

- **Input guard** — every utterance is classified (fine / off-topic / sensitive
  / distress) *before* it reaches the persona LLM. Sensitive and distress
  inputs get fixed, human-written responses — never freeform generation. The
  guard **fails closed**: if classification errors or times out, the safe
  canned path is taken.
- **Output guard** — deterministic sentence-level rules before TTS (no URLs, no
  PII requests, no AI-identity leaks, length cap) with a canned fallback.
- **No-retention posture** — no audio stored, no transcripts persisted, no
  conversation content in logs (metrics only; enforced by tests), Deepgram
  `mip_opt_out=true` on every request.

## Testing

```bash
cd agent && uv run pytest            # 100+ unit tests, fully offline
cd web && npx playwright test        # e2e (auto-starts its own dev server)

# Live persona acceptance script (costs money, needs real keys):
RUN_PERSONA_SCRIPT=1 uv run pytest tests/test_persona_script.py
```

## Repo layout

```
agent/          Python LiveKit agent worker (src layout, uv) + Dockerfile + fly.toml
web/            Next.js frontend (token API, session UI, parent gate)
docs/           research, architecture (+ADRs), build plan, deploy runbook, compliance
BUILD_PLAN.md   original product plan
CLAUDE.md       working notes: commands, decisions, pitfalls
```

## Deploying

Web app on Vercel, agent worker on Fly.io — full runbook with the cost
guardrails in [docs/deploy.md](docs/deploy.md).

## Costs

Avatar minutes dominate (~90% of spend); expect roughly $0.15–0.30 per active
conversation minute across vendors. Sessions hard-stop at `MAX_SESSION_MINUTES`
(default 15) with a friendly sign-off. See `docs/architecture.md` §6.

## Status

Working end-to-end in local development. Before a public deploy, see
`docs/compliance.md` (privacy/COPPA checklist) and the hardening notes in
`docs/review-report.md` — notably, token-endpoint rate limiting needs a
durable store and platform-trusted client IPs.
