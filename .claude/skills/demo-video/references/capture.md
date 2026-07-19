# Capture — programmatic and human paths

Verification status: Playwright/Browserless/screenstudio-cli facts below were
multi-source verified (see `../research/report.md`). Terminal-recording and
OS-screen sections are standard practice but were a coverage gap in the
research — treat as general knowledge and sanity-check versions.

## Playwright (default for web) — verified

Playwright records browser sessions natively, headlessly, with no external
screen recorder. Three ways in:

### 1. Context-level `recordVideo` (simplest)

```js
const { chromium } = require('playwright');

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: 'demo/captures/', size: { width: 1920, height: 1080 } },
});
const page = await context.newPage();
// ... drive the flow ...
await context.close();          // video is finalized on close
const path = await page.video().path();
```

### 2. `page.screencast` (Playwright ≥1.59) — per-scene start/stop

Low-level imperative API for surgical capture: start()/stop() around exactly
one storyboard scene, with timeline annotations. Designed for "tooling,
demos, and surgical capture" (v1.59 release notes). Use this when you want
one clip per scene instead of slicing one long recording.

### 3. Playwright MCP server

If driving the browser through the Playwright MCP server instead of a
script, launch it with `--save-video=1920x1080` to persist session video.

### Facts that will bite you

- **Output is WebM (VP8) only.** No MP4 export exists in Playwright.
  Transcode every clip:
  ```bash
  ffmpeg -i scene-01.webm -c:v libx264 -crf 23 -pix_fmt yuv420p -r 30 scene-01.mp4
  ```
- **Viewport capture, not OS screen.** No browser chrome, no OS cursor —
  which is why the synthetic cursor is added later in Remotion.
- Video file is only finalized after `context.close()` / page close.

### Pacing for demo-quality (not test-speed) capture

Tests run at machine speed; demos must run at human speed:

```js
await page.getByRole('button', { name: 'Export' }).hover();
await page.waitForTimeout(400);          // let the hover state read
await page.getByRole('button', { name: 'Export' }).click();
await page.waitForTimeout(1200);         // hold the result on screen
await page.getByLabel('Title').pressSequentially('My demo', { delay: 70 });
```

- 300–500ms pause after hover, 800–1500ms hold after each meaningful state
  change, 2s hold on the scene's final frame.
- Log a timestamped event per storyboard action (`console.log(JSON.stringify(
  {scene, action, t: Date.now()}))`) so the composite phase knows where
  clicks happened — this drives synthetic-cursor and zoom timing.
- Freshly seed app state before capture (clean test account, deterministic
  data, fixed clock if the UI shows dates) so re-captures are reproducible.

## playwright-recast — when Playwright tests already exist (verified)

MIT npm CLI (v0.19.x, Node 20+, needs `ffmpeg` on PATH) that turns existing
Playwright test artifacts/traces into a narrated MP4 in one command:

```bash
npx playwright-recast -i ./test-results -o demo.mp4 \
  --srt narration.srt --provider elevenlabs --format mp4
```

Providers: `openai | elevenlabs | polly | qwen | none` (API key required for
cloud providers). It synthesizes TTS per subtitle segment, holds frames to
fit narration timing, and merges a continuous soundtrack. Best fit: the
repo already has a Playwright test covering the feature — re-generate the
demo every release instead of re-recording.

## Browserless (cloud alternative) — verified

If local headless capture is impossible, Browserless records WebM
server-side over CDP: connect with `record=true` in the WebSocket string,
call `Browserless.startRecording` / `Browserless.stopRecording`; video data
returns to your code.

## screenstudio-cli (macOS polish path) — verified, with hard caveats

Programmatic control of Screen Studio's editor for agents: timeline
`slice split/trim/speed`, `zoom add --level 2 --x 0.3 --y 0.8`, blur
`mask add --blur 20`, `preview --at 5000` (timestamped screenshot), and
`export`/`render`. Ships its own SKILL.md for Claude Code.

**Caveats (the refuted claim):** it is *not* headless and *not*
terminal-only — it drives the proprietary Screen Studio macOS app over the
Chrome DevTools Protocol (`--remote-debugging-port=9222`). Requires macOS,
a Screen Studio license, and the app running. Use it to polish
human-recorded captures on the user's Mac, not in CI.

## Terminal / CLI demos — general knowledge (research coverage gap)

- `asciinema rec demo.cast` records a terminal session; `agg demo.cast
  demo.gif` renders it; for MP4, play the cast in a browser-based player
  under Playwright capture, or use a terminal-to-video renderer.
- Alternative that composites well: drive commands via a script that types
  them with delays inside a styled xterm.js page, captured by Playwright —
  gives full visual control (font, colors, window chrome).

## Human capture path

For desktop apps, hardware, or real-world footage:

1. Generate a **shot list** from the storyboard — per scene: framing
   ("close-up of left eye display"), the exact action, target duration,
   "hold 2 seconds at the end", orientation (landscape for 16:9 master;
   shoot 4K if the edit will punch in).
2. User records: macOS `screencapture -v` / QuickTime / OBS for screens;
   phone (highest resolution, landscape, locked exposure) for hardware.
3. Normalize everything before editing:
   ```bash
   ffmpeg -i raw.mov -c:v libx264 -crf 20 -pix_fmt yuv420p -r 30 \
     -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
     scene-03.mp4
   ```
4. Rejoin the standard pipeline at Phase 3/4 — human clips and headless
   clips are identical from here on.
