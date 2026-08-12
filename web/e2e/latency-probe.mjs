/**
 * Latency probe: drives a real session with pre-synthesized spoken questions
 * as the fake mic capture, so the agent logs comparable `turn_latency` lines.
 *
 * Usage:
 *   node e2e/latency-probe.mjs /path/to/probe.wav [durationMs] [url]
 *
 * Build the capture file with macOS `say` + `afconvert` (16-bit PCM mono WAV,
 * questions separated by ~14s of silence). Run the agent with idle behaviors
 * disabled so nudges don't contaminate the turns:
 *   IDLE_NUDGE_S=0 IDLE_SHUTDOWN_S=0 uv run python -m commander_sky.main dev
 * Then read the numbers: grep turn_latency <agent log>.
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
page.on("console", (m) => {
  if (m.type() === "error") console.log("CONSOLE_ERR:", m.text().slice(0, 200));
});

await page.goto(url, { waitUntil: "domcontentloaded" });
console.log(`probe started: ${wavPath} for ${durationMs}ms`);
await page.waitForTimeout(Number(durationMs));
await browser.close();
console.log("probe finished — turn_latency lines are in the agent log");
