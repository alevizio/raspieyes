---
name: demo-video
description: >
  Produce a product demo video of an app, website, or feature — storyboard,
  screen capture, AI voiceover, captions, edit, render, and publish. Use when
  the user asks for a demo video, feature walkthrough, launch video, promo
  clip, screen recording of the app, "show how X works", or social cuts
  (YouTube, TikTok/Reels/Shorts, X, LinkedIn) of the product.
---

# Demo Video Production

End-to-end pipeline for turning a feature description into finished demo
videos. Two capture paths (pick per demo), one storyboard as the single
source of truth, multi-format output (16:9 / 9:16 / 1:1) rendered from the
same assets.

**Core stack (verified, mid-2026):** Playwright (headless browser capture) →
FFmpeg (transcode/assemble) → Remotion (programmatic compositing: zooms,
synthetic cursor, captions) → TTS (ElevenLabs / OpenAI / edge-tts) →
per-platform renders. Full evidence and citations: `research/report.md`.

## Hard rules

1. **Human gate #1 — storyboard approval.** Never capture or render before
   the user has approved the storyboard. Every working pipeline in the
   research (Ultrademo, ProductVideoCreator) gates here.
2. **Human gate #2 — final QA.** Never publish or deliver as "done" without
   the user reviewing the render. Automated capture produces subtle failures
   a human must catch: mis-timed narration, awkward cursor paths, wrong UI
   state, layout pops.
3. **One storyboard, many renders.** All aspect ratios and variants re-render
   from the same `storyboard.json` and cached assets. Never re-capture or
   re-bill TTS for a format change.
4. **Playwright records the browser viewport, not the OS screen**, and
   outputs WebM only. Anything outside a browser (desktop apps, hardware,
   terminal) needs the human-capture path or a different recorder.
5. Report costs before spending: TTS is billed per character/token; tell the
   user the estimated cost of narration before synthesizing.

## Pipeline

```
Phase 0  Intake        → what/who/where/format; pick capture path
Phase 1  Storyboard    → beats, shot list, narration script  [USER APPROVES]
Phase 2  Capture       → Playwright headless  |  human-recorded footage
Phase 3  Voiceover     → TTS per scene + SRT captions
Phase 4  Composite     → Remotion: zooms, cursor, captions, music
Phase 5  Render        → 16:9 master, then 9:16 / 1:1 re-renders
Phase 6  QA            → user reviews render                 [USER APPROVES]
Phase 7  Publish       → per-platform files, thumbnail, upload checklist
```

## Phase 0 — Intake

Establish before storyboarding:

- **Subject**: which feature/flow? Scout it first — run the app, click
  through the flow, screenshot key states.
- **Audience & goal**: launch announcement, tutorial, social growth clip?
  This sets tone and length.
- **Primary platform** → master format (see `references/publish.md`):
  - YouTube / landing page → 16:9, 60–180s
  - TikTok / Reels / Shorts → 9:16, 15–60s, hook in first 2 seconds
  - X / LinkedIn feed → 16:9 or 1:1, 30–90s, must work muted
- **Capture path** (decision rule):

| Situation | Path |
|---|---|
| Web app / website flow | **Headless**: Playwright capture (default) |
| CLI / terminal demo | Headless: terminal recording (`references/capture.md`) |
| Desktop app, physical hardware, real-world footage | **Human capture**: user records; you direct the shot list, then edit |
| Web app but maximum cursor/zoom polish on macOS | Hybrid: Screen Studio recording (user-assisted; see caveats in `references/capture.md`) |

## Phase 1 — Storyboard

Write `demo/storyboard.json` from the template at
`templates/storyboard.template.json`. Per scene: id, duration, on-screen
action (as concrete UI steps), narration line, caption text, zoom/focus
region, transition.

Narration style: short declarative sentences, present tense, no filler
("Now we click…" → "Click export. Your video renders in the cloud.").
Target ~140 words/minute of narration; a 60s demo is ~140 words.

Present the storyboard to the user as a readable scene table (not raw
JSON) plus total runtime and estimated TTS cost. **Stop and get approval.**
Iterate here — changes are free at this phase and expensive later.

## Phase 2 — Capture

Full commands and API details: `references/capture.md`.

**Headless path (web):** write a Playwright script that walks the approved
flow. Use `recordVideo` on the context (or `page.screencast` on
Playwright ≥1.59 for start/stop control per scene). Set viewport to the
master resolution (1920×1080 for 16:9; capture 1080×1920 separately only if
a true vertical UI matters — usually the 9:16 cut is composited from the
16:9 capture with zooms instead). Deliberate pacing: add `waitForTimeout`
beats after each action so motion reads on video; type with `delay: 50-80`
so text entry is visible. Transcode WebM → MP4 with FFmpeg.

**Human path:** produce a shot list from the storyboard (per scene: framing,
action, duration, "hold 2s at end"). The user records (screen recorder,
phone for hardware). You take over from the raw files: normalize with
FFmpeg, then continue at Phase 4 exactly as with headless captures.

Per-scene clips named `demo/captures/scene-01.mp4` etc. Verify each clip
plays and matches its storyboard scene (screenshot the midpoint frame and
check UI state) before moving on.

## Phase 3 — Voiceover & captions

Details and pricing: `references/voiceover-captions.md`.

- Synthesize narration **per scene** (one audio file per storyboard scene) —
  this is what lets scenes re-time independently and formats re-render
  without re-billing.
- Provider order of preference: ElevenLabs (best quality; API key needed) →
  OpenAI TTS (`tts-1` $15/1M chars, `tts-1-hd` $30/1M chars) → `edge-tts`
  (free, no key) → macOS `say` (free, offline scratch track).
- Generate `demo/captions.srt` directly from the storyboard narration text
  with measured audio durations — script-derived captions are exact; only
  use Whisper ASR when captioning human-recorded voice.
- Measure each scene's audio duration (`ffprobe`) and write it back into
  the storyboard; scene video length = max(action length, narration length)
  plus breathing room.

## Phase 4 & 5 — Composite and render

Details: `references/render.md`.

Composite in **Remotion** (React → MP4; free for individuals and companies
≤3 employees — check license note in the reference). Install the official
skill first if not present: `npx skills add remotion`. The composition
reads `storyboard.json` and per-scene assets, and applies:

- zoom/pan (Ken Burns) into the storyboard's focus region per scene
- synthetic cursor overlay for click emphasis (headless captures)
- captions from the SRT (burned-in for 9:16 and muted-feed formats)
- title/outro cards, background music ducked under narration

Render order: **16:9 master first**, get it through QA (Phase 6), then
re-render 9:16 and 1:1 from the same composition with reframed focus
regions. If Remotion is unavailable or the edit is trivial (concat + music +
captions), the pure-FFmpeg fallback in `references/render.md` covers it.

## Phase 6 — QA

Send the user the master render (SendUserFile if in a remote session).
Checklist to run yourself before they see it: narration in sync with the
action it describes; no dead air >2s; no wrong UI states (open menus,
half-loaded pages, artifact text); captions legible at target size; audio
levels consistent (narration −16 LUFS-ish, music well under it); first 2
seconds compelling. Fix and re-render until the user approves.

## Phase 7 — Publish

Per-platform specs, thumbnail guidance, and upload checklist:
`references/publish.md`. Deliverables directory:

```
demo/out/
  <name>-16x9.mp4     # YouTube / landing
  <name>-9x16.mp4     # TikTok / Reels / Shorts (captions burned in)
  <name>-1x1.mp4      # X / LinkedIn (captions burned in)
  <name>-thumb.png    # 1280×720 thumbnail
  <name>.srt          # sidecar captions for platforms that accept them
```

Actual uploading is manual or user-authorized per platform — never publish
anywhere without explicit instruction.

## Prior art — reuse before rebuilding

Existing Claude Code skills/tools already implement large parts of this
pipeline; prefer installing one when it fits instead of hand-rolling
(details: `references/prior-art.md`):

- **Ultrademo** (`npx skills add new-xp/ultrademo`) — full pipeline:
  scout → storyboard sign-off → Playwright → TTS → Remotion, all local.
- **playwright-recast** (`npx playwright-recast`) — existing Playwright
  tests/traces → narrated MP4 in one command. Ideal when the repo already
  has Playwright tests covering the feature.
- **Remotion agent skill** (`npx skills add remotion`) — compositing layer.
- **screenstudio-cli** — programmatic zoom/trim/export of Screen Studio
  recordings (macOS + paid app; drives the GUI, not headless).

## This repo (raspieyes)

- **Website demos** (`website/`, Next.js): headless path.
  `cd website && npm install && npm run dev`, then Playwright against
  `http://localhost:3000`.
- **Hardware demos** (the physical eyes): human path — direct a phone shot
  list (eyes tracking a face, pupil dilation close-up, music-reactive pulse,
  startle blink), then edit/caption/render through Phases 3–7. The renderer
  also runs on a dev machine (`python3 eye_renderer.py --mouse --windowed`),
  which can be screen-captured for software-only b-roll.
