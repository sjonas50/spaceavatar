# Deploy Runbook

Two deployables: the Next.js web app (Vercel) and the Python agent worker
(Fly.io). LiveKit, and all AI vendors, are already cloud services.

## 0. Pre-flight (once)

- [ ] Upstash Redis database created (free tier) — copy `UPSTASH_REDIS_REST_URL`
      and `UPSTASH_REDIS_REST_TOKEN`. **Required for a public deploy** — without
      it, rate limiting is per-instance memory and effectively absent on
      serverless.
- [ ] Decide the soft-launch guardrails:
      - `ACCESS_CODE` — set it to require an invite code before any session.
      - `MAX_SESSIONS_PER_DAY` (default 50) — worst-case daily spend is
        roughly `sessions × minutes × ~$0.15`.
- [ ] LiveKit plan: Build (free) is fine for a soft launch. Note (verified
      2026-08-12): "cold start prevention" and the 5-concurrent-agent cap
      apply only to agents *hosted on LiveKit Cloud* — our worker is
      self-hosted on Fly with `min_machines_running=1`, so it is always warm
      and those limits don't apply. What Build actually caps for us is
      WebRTC participant minutes (5,000/mo free; each session consumes
      minutes for visitor + agent + avatar participants) — upgrade to Ship
      ($50/mo, then $0.01/min) when usage approaches that.
- [ ] If the audience may include children: counsel review per
      `docs/compliance.md` **before** the URL is shared.

## 1. Web app → Vercel

1. vercel.com → New Project → import `sjonas50/spaceavatar` → root directory
   **`web/`** (framework auto-detects Next.js).
2. Environment variables (Production):
   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
   - `MAX_SESSION_MINUTES` (e.g. 15)
   - `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
   - `SESSIONS_PER_IP_PER_HOUR` (e.g. 6), `MAX_SESSIONS_PER_DAY` (e.g. 50)
   - `ACCESS_CODE` (recommended for soft launch)
   - Do **not** set `NEXT_PUBLIC_ICE_POLICY` — the TURN-forced default is
     correct for real users (UDP-blocked networks, iPads).
   - `NEXT_PUBLIC_MIC_MODE=ptt` if you want push-to-talk in production.
3. Deploy. Vercel provides HTTPS + a `.vercel.app` domain; add a custom domain
   in project settings if desired.

## 2. Agent worker → Fly.io

From the `agent/` directory:

```bash
fly auth login
fly launch --no-deploy          # accepts existing fly.toml; don't overwrite
fly secrets set \
  LIVEKIT_URL=... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... \
  ANTHROPIC_API_KEY=... DEEPGRAM_API_KEY=... CARTESIA_API_KEY=... \
  AVATAR_MODE=anam ANAM_API_KEY=... ANAM_AVATAR_ID=... \
  TTS_VOICE=...
# ANAM_AVATAR_ID must be an *avatar* ID, not a persona ID (Anam 400s on
# persona IDs). LEMONSLICE_API_KEY/AGENT_ID only if AVATAR_MODE=lemonslice.
fly deploy
fly logs                        # expect: "registered worker ... region US West B"
```

Notes:
- `primary_region` in `fly.toml` is `sjc`; keep it in the same region family as
  your LiveKit project (worker registers in "US West B").
- `min_machines_running = 1` + `auto_stop_machines = false` are deliberate:
  workers hold live WebRTC sessions and must not stop mid-conversation.
- The worker runs `python -m commander_sky.main start` (production mode) via
  the Dockerfile CMD.

## 3. Post-deploy verification

- [ ] Open the production URL: page auto-connects, avatar joins, greeting plays.
- [ ] `fly logs`: `session_started`, `pipeline_metrics`, and `session_cost`
      snapshots every 30s; **no conversation content anywhere**.
- [ ] Rate limit: hit the site more than `SESSIONS_PER_IP_PER_HOUR` times in an
      hour → friendly failure (HTTP 429 under the hood).
- [ ] Wrong/missing access code → mission-code prompt.
- [ ] Test from a phone on cellular (exercises TURN relay).
- [ ] Confirm session hard-stops: 15-minute limit and `MAX_SESSION_COST_USD`.

## Scale checklist (added 2026-08-12)

Concurrency is capped by the **minimum** of three independent limits — raise
them together or the lowest one silently throttles you:

| Layer | Limit | Where to raise |
|---|---|---|
| Anam concurrent sessions | free 1 · Starter 1 · Explorer 3 · Growth 5 · Professional 10 | anam.ai self-serve tiers (ZDR = Enterprise/sales) |
| Anam minutes/month | free 30 · Growth 2,000 · Professional 5,000 | same — when exhausted mid-session the avatar dies; the agent degrades to voice-only (canned "video link dropped" line) |
| LiveKit participant minutes | Build 5,000/mo free; each session burns ~3× wall-clock (visitor + agent + avatar participants) ≈ 1,600 session-min/mo | Ship $50/mo then $0.01/min. NB: LiveKit "cold start prevention"/agent caps apply only to LiveKit-hosted agents — ours is on Fly, always warm |
| Fly machine | 1 shared-cpu machine ≈ dozens of concurrent voice sessions (pipeline is I/O-bound) | `fly scale count 2` + LiveKit dispatches across workers |

Watch in logs: `turn_latency_slo_breach` (>2.5s turn), `avatar_unavailable_voice_only`
(Anam quota/outage at start), `avatar_lost_voice_only_fallback` (mid-session death),
`session_cost` snapshots vs vendor dashboards monthly.

## Cost guardrails summary

| Layer | Control |
|---|---|
| Per session | `MAX_SESSION_MINUTES` (15) + `MAX_SESSION_COST_USD` ($5, enforced by tracker) |
| Per visitor | `SESSIONS_PER_IP_PER_HOUR` (6, Upstash-backed) |
| Per day | `MAX_SESSIONS_PER_DAY` (50, Upstash-backed) |
| Access | `ACCESS_CODE` invite gate |
| Observability | `session_cost` log lines; vendor dashboards for ground truth |
