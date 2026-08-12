# Code Review Report
**Date:** 2026-08-12
**Status:** PASS WITH NOTES

Re-audit following the 2026-07-17 review. All three of that report's top issues are fixed and verified: rate limiting now uses the platform-attested IP + durable Upstash windows (`web/lib/ratelimit.ts`), the `json-repair` CVE floor is pinned (`agent/pyproject.toml:14`), and `MAX_SESSION_COST_USD` is enforced by `SessionCostTracker` + `_cost_cap_loop` (`agent/src/commander_sky/main.py:246-261`).

## Critical Issues (must fix)
1. **Known CVEs in `aiohttp 3.14.1`** — `pip-audit` reports PYSEC-2026-3545/3546/3547 (fixed in 3.14.2/3.14.3); aiohttp is both the direct HTTP client in `agent/src/commander_sky/skytools.py` and the HTTP server behind the publicly routed health port (`agent/fly.toml:33` `http_service` on 8081), so bump and re-lock (`uv lock --upgrade-package aiohttp`) before the next deploy.

## Warnings (should fix)
1. **CLAUDE.md contradicts the code (checklist: "CLAUDE.md accurate and current")** — it says "Anam is ruled out" and `AVATAR_MODE=lemonslice|frontend|none`, but Anam is a supported mode (`agent/src/commander_sky/config.py:18`, `agent/src/commander_sky/avatar.py:56`, `livekit-plugins-anam` in `agent/pyproject.toml:16`); it also claims a "1-hour cache (`cache_control`)" while `main.py:113` uses `caching="ephemeral"` (5-min), and its file map omits `sky_agent.py`, `skytools.py`, `costs.py`, `logging.py`, and `knowledge/`.
2. **Upstash pipeline errors silently disable rate limiting** — `web/lib/ratelimit.ts:63-64`: a per-command error row (`{error: ...}`) leaves `result` undefined, `?? 0` treats it as count 0, and the request is allowed; treat a missing `result` as a failure (throw → memory fallback) instead.
3. **Session-length config still duplicated (carried over, unfixed)** — `MAX_SESSION_MINUTES` must match independently in the web env (token TTL, `web/app/api/token/route.ts:27`) and agent env (`agent/src/commander_sky/config.py:85`); drift cuts sessions short or leaves tokens dangling.
4. **Dockerfile still swallows asset-prefetch failures (carried over, unfixed)** — `agent/Dockerfile:21` `|| true` masks `download-files` errors, silently reintroducing the cold-start penalty the step exists to avoid.
5. **Dev/CI Python is 3.13, production is 3.12** — the local venv runs CPython 3.13.12 (`agent/.venv/pyvenv.cfg`) and CI floats on `requires-python >=3.12`, while `agent/Dockerfile:1` pins 3.12; tests never run on the interpreter that ships — pin 3.12 via `.python-version` or bump the image.

## Suggestions (nice to have)
1. `ACCESS_CODE` check uses non-constant-time `!==` (`web/app/api/token/route.ts:10`) — use `crypto.timingSafeEqual` for hygiene.
2. `_human_count` detects the avatar by the substring `"avatar"` in the identity (`agent/src/commander_sky/main.py:194`) — works for both current plugin defaults (`lemonslice-avatar-agent`, `anam-avatar-agent`) but is fragile; compare against `avatar.avatar_identity` instead.
3. `dry_run()` still uses `assert` for a runtime check (`agent/src/commander_sky/main.py:373`, carried over) — stripped under `python -O`.
4. `search_nasa_image` interpolates `nasa_id` into the asset URL without URL-encoding (`agent/src/commander_sky/skytools.py:120`) — IDs with spaces produce malformed URLs; the HEAD verification masks it as "no usable asset".
5. Visitor tokens grant `canPublishData: true` (`web/app/api/token/route.ts:41`) — the client only receives on the `ui` topic; drop the grant for least privilege.
6. `Settings.model_config` resolves `env_file=("../.env", ".env")` relative to CWD (`agent/src/commander_sky/config.py:32`) — behavior differs when the worker is launched from the repo root vs `agent/`.
7. `clientIp()` trusts `x-real-ip` (`web/lib/ratelimit.ts:36`) — correct on Vercel; re-verify if the web app ever moves platforms, since elsewhere the header can be client-supplied.
8. `entrypoint()` is 79 lines (`agent/src/commander_sky/main.py:264`) — over the 50-line guideline; the watch/limit/cost task wiring could be extracted.
9. Direct deps use ranges, not exact pins, in `pyproject.toml` — acceptable because `uv.lock` + `--frozen` pin the tree in CI/Docker, but it diverges from the stated "pin dependency versions in pyproject" convention.
10. `npm` is unavailable in this environment (also true in the prior review), so `npm audit`/eslint could not run locally — CI (`.github/workflows/ci.yml`) runs lint/build/e2e but not `npm audit`; consider adding an audit step.

## Verified clean
- No hardcoded secrets in any tracked file; only `.env.example` is tracked; `.env*` gitignored with `!.env.example`; all agent keys are `SecretStr`; LiveKit tokens minted server-side only.
- No SQL, no subprocess, no `eval`/`exec` — no injection surface; the browser renders only allowlisted image sources (`/space/` or `https://images-assets.nasa.gov/image/`, enforced agent-side in `skytools.py` and client-side in `SpaceOverlay.tsx:12` plus `next.config.ts` remotePatterns).
- Safety invariants hold: input guard fails closed on timeout/error/unparseable label (`safety.py:126-149`); sensitive/distress → canned-only enforced at the Pydantic layer (`models.py:44-53`); output guard is deterministic and blocks URLs/PII-requests/identity leaks before TTS; guard speculation does not weaken the invariant (persona LLM still awaits the verdict, `sky_agent.py:90-117`).
- COPPA no-content logging holds end-to-end: metrics allowlist (`metrics.py:16`), tags/counts-only logging in guards, tools, and costs; `test_no_content_logging.py` locks it in; Deepgram `mip_opt_out=True` (`main.py:107`).
- Broad `except Exception` blocks (safety, skytools, avatar-start fallback) are all intentional fail-closed/fail-graceful paths that log exception type only — no swallowed exceptions without logging.
- Type hints and Google docstrings on public surfaces; no unused imports/dead code (ruff `F` clean); no circular imports (dry-run import of the full pipeline passes); tests are mock-only (fake creds in `tests/conftest.py`, no live network); cost caps, idle shutdown, session time cap, and visitor-departure cleanup all enforced.

## Metrics
- Files reviewed: 36 (14 agent src, 15 agent tests, 14 web app/lib/components, plus Dockerfile, fly.toml, CI workflows, configs)
- Test count: 253 collected — 214 passed, 39 skipped (live persona-script gate), 0 failed
- Ruff violations: 0 (lint + format clean, 32 files)
- Security issues: 1 critical (aiohttp CVEs), 2 warning (rate-limit error handling, config drift)
