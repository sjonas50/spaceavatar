# Code Review Report
**Date:** 2026-07-17
**Status:** PASS WITH NOTES

## Critical Issues (must fix)
1. **Rate-limit bypass / unbounded spend risk** — `web/app/api/token/route.ts:8` keys the per-IP limit off the first entry of `x-forwarded-for`, which is client-controlled (attacker sends their own XFF; proxies append, not replace), so the 6/hour cap is trivially bypassable; the backstop daily cap in `web/lib/ratelimit.ts:14-18` is per-process memory, so on serverless/multi-instance deploys it is also ineffective — an attacker can mint unlimited sessions at ~$2-4.50 each. Use the platform-trusted IP (e.g. last XFF hop, `request.ip`, or Vercel's `x-real-ip`) and a durable store (Upstash/Redis) before any public deploy.

## Warnings (should fix)
1. **Known CVE in prod dependency tree** — `json-repair 0.59.10` (transitive via `livekit-agents`) has GHSA-xf7x-x43h-rpqh; fix version 0.60.1 (`agent/uv.lock`). Add a constraint and re-lock.
2. **Session cost cap is not enforced** — `agent/src/commander_sky/config.py:53` defines `max_session_cost_usd` (and CLAUDE.md/BUILD_PLAN promise a cost cap), but nothing reads it; only the time cap in `main.py:104` is enforced.
3. **Dead observability models** — `TurnMetrics` and `SessionLimits` (`agent/src/commander_sky/models.py:56-73`) are used only by tests; `guard_ms` latency is never measured anywhere.
4. **Fly build context likely broken** — `agent/Dockerfile:10` copies `pyproject.toml` from the build-context root, but the documented deploy command (`infra/fly.toml:3`, run from repo root) makes the repo root the context, where no `pyproject.toml` exists; the build will fail. Verify/deploy with `agent/` as context.
5. **Dockerfile swallows asset-prefetch failures** — `agent/Dockerfile:21` `|| true` masks `download-files` errors, silently reintroducing the cold-start penalty the step exists to avoid.
6. **No user feedback on mic-permission denial** — `web/components/PushToTalkButton.tsx:16-26` has no catch around `setMicrophoneEnabled`; a denied permission is an unhandled rejection and the child sees nothing happen.
7. **No root README.md** — setup lives only in `CLAUDE.md`; the checklist requires a README with setup instructions (`web/README.md` is untouched Next.js boilerplate).
8. **Duplicated session-length config** — `MAX_SESSION_MINUTES` must independently match in the web env (`route.ts:22`, token TTL) and agent env (`config.py:52`); drift silently cuts sessions short or leaves tokens dangling. Document or centralize.

## Suggestions (nice to have)
1. `_URL_RE` in `agent/src/commander_sky/safety.py:97` misses `.gov`/`.edu` and spoken forms ("nasa dot gov") — ironic for a space app whose most likely URL is nasa.gov.
2. `_SCARY_RE` (`safety.py:108`) is a narrow blocklist ("kill you" matches but "kill him"/"knife"/"died" do not); treat it as defense-in-depth and keep expanding from red-team transcripts.
3. `dry_run()` uses `assert` for a runtime check (`agent/src/commander_sky/main.py:177`) — stripped under `python -O`; use an explicit check.
4. Per-instance rate-limit state is already flagged in `ratelimit.ts:8-9`; prioritize the durable-store move together with Critical #1.
5. `npm audit` / eslint could not run in this environment (npm unavailable); run them in CI to close the JS-dependency audit gap.
6. Pytest emits a `DeprecationWarning` from `livekit agent_session` event-loop handling — watch on the next `livekit-agents` bump.

## Verified clean
- No hardcoded secrets anywhere; all keys are `SecretStr` env vars server-side; `.env*` gitignored with `!.env.example` (`.gitignore:17-20`); no secrets in git history filenames.
- No SQL, no subprocess, no shell-out — no injection surface.
- Fail-closed input guard verified (timeout, API error, unparseable label → canned sensitive response), invariants enforced at the Pydantic layer (`models.py:44-53`).
- COPPA no-content-logging rule holds: guards/metrics log tags and numbers only; `test_no_content_logging.py` locks it in; Deepgram `mip_opt_out=True` set (`main.py:80`).
- The one broad `except Exception` (`safety.py:90`) is intentional fail-closed behavior and logs the exception type — acceptable.
- Type hints, Google docstrings, ruff (0 violations, 24 files formatted), all functions under 50 lines, no circular imports, mocked-only tests (no network), conftest fixtures present.

## Metrics
- Files reviewed: 30 (12 agent src, 11 agent tests, 12 web, plus config/infra)
- Test count: 134 collected — 102 passed, 32 skipped (live persona script, gated on `RUN_PERSONA_SCRIPT=1`)
- Ruff violations: 0 (lint + format clean)
- Security issues: 1 critical, 2 warning (CVE + unenforced cost cap)
