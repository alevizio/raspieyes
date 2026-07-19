# Prior art — existing tools that implement this pipeline

All entries verified against primary repos (mid-2026). These are new,
single-vendor projects: verified as *documented to work this way*, not as
battle-tested in production. Prefer reusing them when they fit; fall back to
the hand-rolled pipeline in this skill when they don't.

## Ultrademo — full pipeline as a Claude Code skill

- Install: `npx skills add new-xp/ultrademo` · https://github.com/new-xp/ultrademo
- Flow: scouts your app → drafts a scene-by-scene script **for your
  sign-off** → a flow file drives Playwright through the app → TTS voices
  each line → Remotion renders with zooms, a synthetic cursor, and captions.
- Everything runs locally ("your renders never leave it") — though choosing
  cloud TTS (ElevenLabs) does send narration text out.
- One storyboard → re-renders to 16:9 MP4, vertical 9:16, GIF, captions-off
  variants, without re-capturing or re-billing TTS.
- **When to use:** web-app demo, standard look, minimum custom work.

## ProductVideoCreator — five-phase pipeline, 8 sub-skills

- https://github.com/MatrixReligio/ProductVideoCreator — copied into
  `.claude/skills/`, auto-discovered by Claude Code.
- Stack: Remotion + Playwright + `edge-tts` (free TTS) + FFmpeg.
- Fixed phases: Storyboard Design (**requires user approval**) → Asset
  Preparation → Voiceover Generation → Video Composition → Review & Delivery.
- **When to use:** zero-API-key requirement (edge-tts is free); good
  reference architecture — this skill's phase structure mirrors it.

## playwright-recast — Playwright tests → narrated MP4

- MIT, npm (`playwright-recast`, v0.19.x), Node 20+, ffmpeg on PATH.
- `npx playwright-recast -i ./test-results -o demo.mp4 --srt narration.srt
  --provider elevenlabs` — providers `openai|elevenlabs|polly|qwen|none`.
- Synthesizes TTS per subtitle segment, frame-holds to fit narration,
  merges continuous soundtrack; subtitles derivable from trace BDD steps.
- **When to use:** the feature already has Playwright test coverage —
  regenerate the demo each sprint instead of re-recording.

## Remotion agent skill — compositing layer

- `npx skills add remotion` (also `npx remotion skills add`) ·
  https://www.remotion.dev/docs/ai/coding-agents
- Official coding-agent support (Claude Code, Codex, Kimi Code, OpenCode,
  Cursor); one of the most-installed skills on skills.sh.
- License: free for individuals / ≤3-employee for-profits / non-profits;
  Company License beyond that; "Automators" pricing ($0.01/render,
  $100/mo minimum) targets automation platforms, not local personal renders.

## screenstudio-cli — programmatic Screen Studio editing (macOS)

- https://github.com/ShawnPana/screenstudio-cli — built for AI agents,
  ships its own SKILL.md with command reference + crash-prevention rules.
- Verified command surface: `slice split 15000`, `slice trim`,
  `slice speed 0 2.0`, `zoom add 0 --level 2 --x 0.3 --y 0.8`, `zoom split`,
  `mask add … --blur 20`, `preview --at 5000`, `export` / `render`.
- **Not headless** (this framing was explicitly refuted in verification):
  it drives the paid, proprietary Screen Studio macOS app over CDP
  (`--remote-debugging-port=9222`). Needs macOS + license + the app running.
- **When to use:** polishing human-made recordings on the user's Mac with
  Screen Studio's auto-zoom/cursor-smoothing aesthetic.

## Claude-Code-Video-Toolkit — grab-bag

- https://github.com/wilwaldon/Claude-Code-Video-Toolkit — skills/MCP
  servers for Remotion, Manim, screen recording, YouTube clipping, FFmpeg
  post-processing. Browse when a niche need isn't covered above.
