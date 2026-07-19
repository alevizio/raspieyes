# Composite & render — Remotion first, FFmpeg fallback

## Remotion (primary) — verified

React components → MP4. No timeline editor. Officially supports coding
agents (Claude Code, Codex, Kimi Code, OpenCode, Cursor) and ships an
installable agent skill:

```bash
npx skills add remotion        # or: npx remotion skills add
```

Install that skill and follow it for composition specifics; this reference
covers only the demo-video-specific architecture.

### Licensing / pricing (verified, mid-2026 — recheck before relying on it)

- **Free** (including commercial use) for: individuals, for-profit companies
  with ≤3 employees, non-profits. Source-available, not fully open-source.
- Larger companies need a paid Company License.
- "Remotion for Automators" ($0.01/render, $100/month minimum) applies to
  automation/rendering-as-a-service products — not to rendering your own
  demos locally as an individual.

### Composition architecture

One composition, driven entirely by `storyboard.json`:

```
<Composition id="Demo" ...>            // dimensions from format param
  {scenes.map(scene =>
    <Sequence from={scene.startFrame} durationInFrames={scene.frames}>
      <SceneVideo src={scene.capture} zoom={scene.focus} />   // Ken Burns into focus region
      <Cursor events={scene.clicks} />                        // synthetic cursor (headless captures)
      <Captions text={scene.caption} />                       // from SRT, styled per format
      <Audio src={scene.narration} />
    </Sequence>)}
  <Audio src="music.mp3" volume={ducked} />                   // ducked under narration
</Composition>
```

- **Zoom/pan (Ken Burns):** interpolate scale 1.0 → ~1.4 toward the scene's
  `focus` region ({x, y, w, h} in 0–1 coordinates from the storyboard).
  Ease in/out; never cut zoom levels abruptly mid-scene.
- **Synthetic cursor:** animate a cursor sprite between the click
  coordinates logged during capture; scale-pulse on click. Only for
  headless captures (human screen recordings already show a cursor).
- **Captions:** render from the SRT with per-format styling — 9:16 gets
  large centered captions in the safe area; 16:9 gets lower-third.
- **Music:** constant low volume, dip (duck) ~6–10 dB under narration
  segments. Music sourcing was a research coverage gap — use only tracks
  the user provides or confirms are licensed/royalty-free.

### Multi-format from one storyboard (verified pattern)

Parameterize the composition on `{width, height, layout}` and re-render:

```bash
npx remotion render Demo out/demo-16x9.mp4 --props='{"format":"16x9"}'
npx remotion render Demo out/demo-9x16.mp4 --props='{"format":"9x16"}'
npx remotion render Demo out/demo-1x1.mp4  --props='{"format":"1x1"}'
```

For 9:16 from a 16:9 capture: don't letterbox — punch into the focus region
(the storyboard's `focus` box tells you where the action is), stack a title
above and captions below. Narration/TTS is reused as-is (never re-billed);
only layout changes.

## FFmpeg fallback (no Remotion, or trivial edits)

Concat scenes + narration + music + burned captions without Remotion:

```bash
# 1. concat scene clips (same codec/size/fps)
printf "file '%s'\n" demo/captures/scene-*.mp4 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy demo-silent.mp4

# 2. concat per-scene narration to one track (with silences pre-padded)
ffmpeg -f concat -safe 0 -i audio-list.txt -c:a aac narration.m4a

# 3. mux narration + ducked music (sidechain compression)
ffmpeg -i demo-silent.mp4 -i narration.m4a -i music.mp3 -filter_complex \
 "[2:a]volume=0.25[m];[1:a][m]sidechaincompress=threshold=0.05:ratio=8[mix];[1:a][mix]amix=inputs=2[a]" \
 -map 0:v -map "[a]" -c:v copy -shortest demo-audio.mp4

# 4. burn captions
ffmpeg -i demo-audio.mp4 -vf "subtitles=demo/captions.srt:force_style='FontSize=22,Outline=1'" \
  -c:a copy out/demo-16x9.mp4

# 9:16 crop-punch from 16:9 (center the focus region via the crop x offset)
ffmpeg -i out/demo-16x9.mp4 -vf "crop=608:1080:656:0,scale=1080:1920" out/demo-9x16.mp4
```

Zoom/pan is possible in FFmpeg (`zoompan`) but fiddly; if the demo needs
per-scene zooms and a synthetic cursor, use Remotion.

## Motion Canvas / Rotato / others

Named in the research question but not covered by any verified claim
(coverage gap). Motion Canvas is a code-driven animation alternative to
Remotion (TypeScript generators, editor-preview-centric); Rotato does 3D
device mockups. Evaluate fresh if the user asks; don't recommend from here.

## Render QC targets

- H.264 (`libx264`), `-pix_fmt yuv420p` (compatibility), CRF 18–23, 30 fps.
- Audio AAC 192k+, narration loudness ≈ −16 LUFS (`ffmpeg -af loudnorm`).
- First and last frames: no half-loaded UI, no cursor mid-flight.
- Watch the full render (or sample every scene boundary via
  `ffmpeg -ss ... -frames:v 1`) before showing the user.
