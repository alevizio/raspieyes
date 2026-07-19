# Deep research: agent-driven demo-video production (2025–2026)

Produced 2026-07-19 by a fan-out research workflow: 6 search angles →
24 sources fetched → 67 claims extracted → top 25 adversarially verified
(3 independent votes each) → 23 confirmed, 2 refuted. This report backs
`../SKILL.md`; confidence labels below reflect those votes.

## Summary

An AI coding agent can drive a genuinely end-to-end product-demo pipeline
today. Purpose-built Claude Code skills already exist (Ultrademo,
ProductVideoCreator) and converge on the same stack this skill uses:
**Playwright** for headless browser capture (WebM native, FFmpeg transcode
to MP4), **Remotion** for programmatic compositing (zooms, synthetic
cursor, captions, multi-aspect re-renders from one storyboard), and
**ElevenLabs / OpenAI TTS / edge-tts** for narration. The pipeline is
automatable headlessly from capture through render. The one universally
human-gated step is **storyboard/script approval**; the weakest-automated
links are cursor/zoom polish and publishing/thumbnails.

## Verified findings

### 1. End-to-end agent skills already exist — HIGH (3-0 × 6 claims)

Ultrademo (`npx skills add new-xp/ultrademo`) and ProductVideoCreator
(`.claude/skills/`, auto-discovered) both: scout the app → draft a
scene-by-scene script for human sign-off → capture with Playwright →
TTS narration → render locally with Remotion + FFmpeg. Ultrademo: "drives
Playwright through your app… TTS voices each line… Remotion renders the
result with zooms, a synthetic cursor, and captions… Everything runs on
your machine." ProductVideoCreator: fixed five-phase pipeline, Storyboard
Design **requires user approval**.
Sources: github.com/new-xp/ultrademo · ultrademo.net ·
github.com/MatrixReligio/ProductVideoCreator

### 2. Playwright is the capture layer — HIGH (3-0 × 7 claims)

- `recordVideo: { dir }` context option / Test-config `video` option.
- `page.screencast` start/stop API since **1.59**, with timeline
  annotations, "for tooling, demos, and surgical capture".
- Playwright MCP server flag `--save-video=1920x1080`.
- Output **WebM (VP8) only**; MP4 requires FFmpeg
  (`ffmpeg -i video.webm -c:v libx264 -crf 23 video.mp4`).
- Records the browser **viewport, not the OS screen**.
- Cloud alternative: Browserless CDP recording (`record=true` +
  `Browserless.startRecording/stopRecording`). Puppeteer covers the same
  ground in CI.
Sources: playwright.dev/docs/videos · playwright v1.59 release ·
docs.browserless.io · trion-development/screen-capture-puppeteer-playwright

### 3. Remotion is the compositing layer — HIGH (3-0 × 5 claims)

React → MP4, no timeline editor. Official coding-agent support (Claude
Code, Codex, Kimi Code, OpenCode, Cursor); installable agent skill
(`npx remotion skills add` / `npx skills add remotion`), among the
most-installed skills on skills.sh (~#4, 126k+ installs). One storyboard →
16:9/9:16/GIF/captions-off variants without re-capturing or re-billing
TTS. **License:** source-available; free for individuals, ≤3-employee
for-profits, non-profits; Company License beyond that; "Remotion for
Automators" $0.01/render + $100/mo minimum (automation businesses, not
local personal renders). Current as of May 2026.
Sources: remotion.dev/docs/ai/coding-agents · remotion.dev/docs/license

### 4. TTS narration is fully automatable per-segment — HIGH (3-0 × 3 claims)

playwright-recast (MIT, npm v0.19.2 published 2026-07-15, ~4.8k
downloads/mo) converts Playwright traces into narrated MP4s in one
command: `npx playwright-recast -i ./test-results -o demo.mp4 --srt
narration.srt --provider elevenlabs`. Providers
`openai|elevenlabs|polly|qwen|none`; per-subtitle synthesis, frame-hold
timing, soundtrack merge. Requires ffmpeg on PATH, Node 20+, provider key.
Verified against the published dist/cli.js, not just the README.
Sources: npmjs.com/package/playwright-recast ·
github.com/ThePatriczek/playwright-recast

### 5. Zoom/cursor polish via screenstudio-cli — HIGH with caveat (3-0 × 2; 1 refuted)

Agent-ready CLI (ships a SKILL.md for Claude Code/Codex): `slice
split/trim/speed`, `zoom add --level --x --y`, `mask add --blur`,
`preview --at`, `export`/`render`. **Refuted framing:** it is *not*
terminal-only/headless — it drives the proprietary Screen Studio macOS app
over CDP (`--remote-debugging-port=9222`); needs macOS + license.
Source: github.com/ShawnPana/screenstudio-cli

### 6. TTS pricing — MEDIUM (2-1)

OpenAI `tts-1` **$15/1M characters**, `tts-1-hd` **$30/1M characters**
(corroborated). `gpt-4o-mini-tts` "$0.60/1M" is per input **token** (not
character) and omits the dominant audio-output-token cost (~$12/1M,
≈$0.015/min) — do not quote $0.60 as the cost.
Source: vapi.ai/blog/elevenlabs-vs-openai (cross-checked against OpenAI docs)

## Refuted claims (do not repeat)

1. "screenstudio-cli lets you record, edit, and export entirely from the
   terminal, without touching the GUI" — **refuted 1-2**. It automates the
   GUI app via CDP.
2. "ElevenLabs tiers: Starter 30k chars $5, Creator 100k $22, Pro 500k
   $99, Scale 2M $330" — **refuted 0-3**. ElevenLabs pricing is
   unverified; check elevenlabs.io before quoting any figure.

## Caveats

- Ultrademo/ProductVideoCreator/playwright-recast/screenstudio-cli are new
  2026 single-vendor repos: verified as *documented*, not as
  production-proven.
- Everything is time-sensitive to mid-2026 versions and pricing
  (Playwright ≥1.59, Remotion license terms, OpenAI TTS rates).
- "Everything runs locally" breaks if cloud TTS is selected (narration
  text leaves the machine).

## Coverage gaps (no verified claims — treat as inference in the skill)

macOS `screencapture` · OBS · asciinema · Chrome DevTools Recorder ·
Motion Canvas · Rotato · thumbnail generation · background-music sourcing ·
automated publishing/upload (YouTube Data API, TikTok/LinkedIn APIs).

## Open questions

1. Is any agent-drivable upload/thumbnail automation reliable, or is
   publishing fully manual? (Least-evidenced link.)
2. How well do these pipelines handle non-browser capture (CLI, native
   desktop, OS-level recording)?
3. Beyond storyboard approval, which steps need human QA in practice
   (mis-timed narration, awkward cursor paths, wrong UI states)?
4. What royalty-free music sourcing and caption-accuracy options (ASR vs
   script-derived SRT) integrate cleanly, and at what cost?

## Source quality ledger

Primary: new-xp/ultrademo, MatrixReligio/ProductVideoCreator,
ShawnPana/screenstudio-cli, playwright.dev/docs/videos,
docs.browserless.io, trion-development/screen-capture-puppeteer-playwright,
remotion.dev/docs/license, remotion.dev/docs/ai/coding-agents,
npmjs.com/package/playwright-recast.
Blogs (corroborating): dev.to/thepatriczek, qaskills.sh,
vapi.ai, localaimaster.com, demopolish.com, peterclaridge.com,
wilwaldon/Claude-Code-Video-Toolkit.
Rejected as unreliable during extraction: mcpmarket.com, mindstudio.ai,
pkgpulse.com, pexo.ai, deepgram.com listicle, williamhuster.com,
matte.app, demosmith.ai.
