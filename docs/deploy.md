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
- [ ] LiveKit plan: Build (free) is fine for a soft launch; Ship ($50/mo)
      removes 10–20s worker cold starts and the 5-concurrent-agent cap.
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
  LEMONSLICE_API_KEY=... LEMONSLICE_AGENT_ID=...
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

## Cost guardrails summary

| Layer | Control |
|---|---|
| Per session | `MAX_SESSION_MINUTES` (15) + `MAX_SESSION_COST_USD` ($5, enforced by tracker) |
| Per visitor | `SESSIONS_PER_IP_PER_HOUR` (6, Upstash-backed) |
| Per day | `MAX_SESSIONS_PER_DAY` (50, Upstash-backed) |
| Access | `ACCESS_CODE` invite gate |
| Observability | `session_cost` log lines; vendor dashboards for ground truth |
