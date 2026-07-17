# Compliance Checklist — Commander Sky

**Status:** pre-launch working document · **Owner:** TBD · **Counsel review: REQUIRED before launch**

## Architecture posture (built, verified in code)

| Control | Where | Status |
|---|---|---|
| No audio persistence — stream to STT, discard | agent pipeline (no recording anywhere) | ✅ built |
| No transcripts persisted | no storage layer exists; nothing written | ✅ built |
| No conversation content in logs | `metrics.py` numeric allowlist + `test_no_content_logging.py` | ✅ built + tested |
| Deepgram model-improvement opt-out | `mip_opt_out=True` on every STT connection (`main.py`) | ✅ built |
| Mic posture | `SessionExperience.tsx` (`NEXT_PUBLIC_MIC_MODE`) | ⚠️ **CHANGED 2026-07-17: owner switched default to always-on open mic** (auto-connect on page load, continuous audio streaming, mute toggle). Push-to-talk still available via `NEXT_PUBLIC_MIC_MODE=ptt`. **Counsel must review open-mic before launch** — continuous capture of child audio weakens the "collect to fulfill request, delete promptly" COPPA argument that push-to-talk supported. |
| No child camera use | `video={false}` in session page | ✅ built |
| Anonymous sessions (random UUID room/identity, short TTL) | `app/api/token/route.ts` | ✅ built |
| Avatar never asks for personal info | persona rules + output guard `pii_request` + tests | ✅ built + tested |
| Session length cap with friendly sign-off | `MAX_SESSION_MINUTES`, `_end_session_after_limit` | ✅ built |
| Per-IP and daily session caps | `web/lib/ratelimit.ts` | ✅ built (in-memory; durable store before scale) |

## Vendor actions (open — must close before launch)

| Vendor | Action | Status |
|---|---|---|
| Anthropic | Request Zero Data Retention via sales; confirm minors-guidance compliance (age gate is parental, content filtered, AI disclosed to parents) | ☐ open |
| Deepgram | Execute DPA; written confirmation of audio deletion timeline post-transcription | ☐ open |
| Cartesia | Audit data-retention posture + DPA (not yet reviewed — flagged in research) | ☐ open |
| LemonSlice | DPA + retention terms; confirm no training on session data; confirm ToS permits child-directed use | ☐ open |
| LiveKit | Sign DPA; confirm zero-retention transit posture in writing; TURN relay verified on school networks | ☐ open |
| ElevenLabs | Only if used for voice design: written confirmation that TTS-output-to-children is permitted under ToS | ☐ open |

## COPPA (amended rule) requirements

- [ ] Written data-retention policy published (purposes, business need, deletion timeline) — even with a no-retention architecture, the policy must exist in writing.
- [ ] Privacy policy written for parents; plain language.
- [ ] Direct notice + verifiable parental consent flow **if** any personal information is collected. Current architecture collects none by design — counsel must confirm the no-retention design keeps us outside the consent trigger, including biometric (voiceprint) handling by vendors during processing.
- [ ] Separate consent required before any child data could ever be used for AI training — currently prohibited across all vendor configs; keep it that way.
- [ ] Confirm voice audio flow (browser → LiveKit → Deepgram, transient) qualifies as "collect to fulfill request, delete promptly" under FTC guidance.

## Pre-launch verification

- [ ] Red team: ≥200 adversarial exchanges, zero unsafe outputs (repeat before every major release).
- [ ] Persona script live run (`RUN_PERSONA_SCRIPT=1`) + human spot check.
- [ ] Accuracy review of `facts/` by a space-knowledgeable reviewer.
- [ ] Kid usability test (≥5 kids, observed, supervised).
- [ ] Load test at target concurrency; verify vendor concurrency caps (LemonSlice sessions, Cartesia streams, LiveKit agents).
- [ ] Latency SLO verified: ≤1.2s p50 / ≤2s p95 utterance-end → first audio.
- [ ] Counsel sign-off on this document.
