/**
 * Latency probe: drives a real session with pre-synthesized spoken questions
 * as the fake mic capture, so the agent logs comparable `turn_latency` lines —
 * and measures *perceived* latency in-browser: end of spoken question (mic
 * energy falls) → response audio onset (remote track energy rises). With an
 * avatar, remote audio is the avatar's republished track synced to video, so
 * audio onset ≈ lips moving.
 *
 * Usage:
 *   node e2e/latency-probe.mjs /path/to/probe.wav [durationMs] [url]
 *
 * Build the capture file with macOS `say -v <voice>` + `afconvert` (16-bit PCM
 * mono WAV, questions separated by ~14s of silence). Run the agent with idle
 * behaviors disabled so nudges don't contaminate the turns:
 *   IDLE_NUDGE_S=0 IDLE_SHUTDOWN_S=0 uv run python -m commander_sky.main dev
 * Serial-path numbers: grep turn_latency <agent log>. Perceived numbers: this
 * script's stdout table.
 */
import { chromium } from "playwright";

const [wavPath, durationMs = "115000", url = "http://localhost:3000"] =
  process.argv.slice(2);
if (!wavPath) {
  console.error("usage: node e2e/latency-probe.mjs <probe.wav> [durationMs] [url]");
  process.exit(1);
}

const browser = await chromium.launch({
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${wavPath}`,
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const page = await browser.newContext({ permissions: ["microphone"] }).then((c) => c.newPage());

/** @type {{kind: string, event: string, t: number}[]} */
const events = [];
page.on("console", (m) => {
  const text = m.text();
  if (text.startsWith("[probe]")) {
    const [, kind, event, t] = text.split(" ");
    events.push({ kind, event, t: Number(t) });
    console.log(text);
    return;
  }
  if (m.type() === "error") console.log("CONSOLE_ERR:", text.slice(0, 200));
});

// Energy monitors, injected before the app loads. Each monitored stream logs
// "[probe] <kind> ON|OFF <performance.now()>" on speech transitions. OFF fires
// after a hangover so intra-sentence pauses don't split a question, but is
// stamped with the time the energy actually dropped.
await page.addInitScript(() => {
  const ON_RMS = 0.01;
  const POLL_MS = 25;
  const HANGOVER_MS = 700;
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  // Wall-clock anchor so probe timestamps can be aligned with agent log lines.
  console.log(`[probe] EPOCH OFFSET ${(Date.now() - performance.now()).toFixed(0)}`);

  function monitor(stream, kind) {
    if (!stream.getAudioTracks().length) return;
    ctx.resume();
    const src = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    src.connect(an);
    const buf = new Float32Array(an.fftSize);
    let speaking = false;
    let lastAbove = 0;
    setInterval(() => {
      an.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();
      if (rms > ON_RMS) {
        if (!speaking) {
          speaking = true;
          console.log(`[probe] ${kind} ON ${now.toFixed(0)}`);
        }
        lastAbove = now;
      } else if (speaking && now - lastAbove > HANGOVER_MS) {
        speaking = false;
        console.log(`[probe] ${kind} OFF ${lastAbove.toFixed(0)}`);
      }
    }, POLL_MS);
  }

  // Local side: tap whatever stream the app gets from the (fake) mic.
  const realGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = async (constraints) => {
    const stream = await realGUM(constraints);
    monitor(stream, "MIC");
    return stream;
  };

  // Remote side: tap every media element the app attaches a stream to.
  const tapped = new WeakSet();
  let remoteIdx = 0;
  setInterval(() => {
    for (const el of document.querySelectorAll("audio, video")) {
      const stream = el.srcObject;
      if (stream instanceof MediaStream && !tapped.has(stream)) {
        tapped.add(stream);
        monitor(stream, `REMOTE${remoteIdx++}:${el.tagName.toLowerCase()}`);
      }
    }
  }, 250);
});

await page.goto(url, { waitUntil: "domcontentloaded" });
console.log(`probe started: ${wavPath} for ${durationMs}ms`);
await page.waitForTimeout(Number(durationMs));
await browser.close();

// Pair each end-of-question (MIC OFF) with the next response onset (any
// REMOTE* ON) to get the perceived gap the visitor experiences.
const micOffs = events.filter((e) => e.kind === "MIC" && e.event === "OFF");
const remoteOns = events.filter((e) => e.kind.startsWith("REMOTE") && e.event === "ON");
console.log("\nturn | question_end_ms | response_on_ms | perceived_gap_ms");
micOffs.forEach((off, i) => {
  const on = remoteOns.find((e) => e.t > off.t);
  console.log(
    `${i + 1} | ${off.t.toFixed(0)} | ${on ? on.t.toFixed(0) : "-"} | ${
      on ? (on.t - off.t).toFixed(0) : "no response"
    }`,
  );
});
console.log("probe finished — turn_latency lines are in the agent log");
