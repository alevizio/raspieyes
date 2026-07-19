# Voiceover & captions

## Provider choice

Ranked for demo narration. Always synthesize **per scene** (one file per
storyboard scene) so re-edits and format re-renders never re-bill TTS.

| Provider | Quality | Cost (verified where noted) | Notes |
|---|---|---|---|
| ElevenLabs | Best-in-class naturalness | Subscription tiers — **pricing not verified in our research; check elevenlabs.io before quoting numbers to the user** | Needs API key. The default in Ultrademo/playwright-recast for a reason. |
| OpenAI `tts-1` | Very good | **$15 / 1M characters** (verified) | ~60s demo ≈ 140 words ≈ 800 chars ≈ **$0.012**. Effectively negligible. |
| OpenAI `tts-1-hd` | Better | **$30 / 1M characters** (verified) | Same math ×2. |
| OpenAI `gpt-4o-mini-tts` | Good | $0.60/1M **input tokens** — beware: that rate excludes audio *output* tokens (~$12/1M, ≈$0.015/min), which dominate. Don't quote the $0.60 figure as the cost. | Verified-with-caveat. |
| `edge-tts` (Python, free) | Decent neural voices | Free, no API key | What ProductVideoCreator uses. Good default when no keys are available. |
| macOS `say` / Piper | Robotic–okay | Free, offline | Scratch tracks and timing drafts; swap for a real provider before final render. |

Cost etiquette: compute total characters across the storyboard, state the
estimated cost, get a nod before synthesizing with a paid provider.

### Synthesis loop

```bash
# example: edge-tts (free) per scene
edge-tts --voice en-US-GuyNeural --text "$(jq -r '.scenes[0].narration' storyboard.json)" \
  --write-media demo/audio/scene-01.mp3

# measure duration, write back into storyboard
ffprobe -v error -show_entries format=duration -of csv=p=0 demo/audio/scene-01.mp3
```

For OpenAI: POST `/v1/audio/speech` with `model: tts-1`, `voice`, `input`.
For ElevenLabs: text-to-speech endpoint with a chosen voice ID.

Scene video duration = max(capture length, narration length) + ~0.5s
breathing room. If narration overruns the capture, hold the final frame
(freeze) rather than speeding up the voice.

## Captions

Two sources, pick by path:

1. **Script-derived (default, exact):** you already have the narration text
   and each scene's measured audio duration — emit the SRT directly.
   Distribute line timings within a scene proportionally to word count.
   No ASR errors, zero cost.
2. **Whisper ASR (human-recorded voice only):** when the user records their
   own voiceover, transcribe with Whisper (open-source, runs locally) to
   get timed captions, then hand-correct product names. (General knowledge —
   this was a research coverage gap.)

SRT format sanity: sequential indices, `HH:MM:SS,mmm` comma decimals,
≤2 lines & ≤42 chars/line per cue.

Styling at render time (see `render.md`): burned-in for 9:16/1:1 and any
muted-autoplay platform; sidecar `.srt` for YouTube uploads.

## Narration writing rules

- Present tense, active, second person where natural ("Drop in your file.
  Claude storyboards the demo.").
- One idea per scene; the narration describes what the viewer *sees now*.
- ~140 wpm budget. Scene narration that reads longer than the scene's
  action → cut words before holding frames.
- Read the full script aloud once (or TTS a scratch pass with a free
  provider) to catch tongue-twisters before paying for the final voice.
