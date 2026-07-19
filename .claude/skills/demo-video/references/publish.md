# Publish — formats, thumbnails, upload

Status note: automated publishing was the least-evidenced link in the
research (no verified claims for upload APIs or thumbnail automation).
Platform specs below are general knowledge, stable but worth a spot-check
if a platform rejects an upload. Never upload anywhere without the user's
explicit go-ahead.

## Per-platform matrix

| Platform | Aspect | Resolution | Length sweet spot | Sound | Captions |
|---|---|---|---|---|---|
| YouTube (standard) | 16:9 | 1920×1080+ | 60–180s for feature demos | On | Sidecar `.srt` upload |
| YouTube Shorts | 9:16 | 1080×1920 | ≤60s | On | Burned-in |
| TikTok / IG Reels | 9:16 | 1080×1920 | 15–45s, hook ≤2s | On, music matters | Burned-in |
| X (Twitter) | 16:9 or 1:1 | 1280×720 / 1080×1080 | 30–90s | **Autoplay muted** | Burned-in |
| LinkedIn | 1:1 or 16:9 | 1080×1080 / 1920×1080 | 30–90s | **Autoplay muted** | Burned-in |
| Landing page / README | 16:9 | 1920×1080; also export a lightweight `.webm`/`.gif` loop | 10–30s loop, silent | Muted loop | Optional |

Encoding for all: H.264 + AAC MP4, `yuv420p`, 30fps, CRF 18–23.

## Format-specific edits (not just crops)

- **9:16**: punch into the focus region, big captions, title card top third.
  Cut length aggressively — keep only the 2–3 strongest scenes.
- **Muted-feed formats (X/LinkedIn)**: the video must make sense with zero
  audio — captions carry the narration, first frame is a readable hook.
- **README/landing loop**: strip audio, trim to the single best interaction,
  `ffmpeg -i in.mp4 -an -t 15 loop.mp4`; GIF only if the host requires it
  (GIFs are huge — prefer `.webm`/`.mp4`).

## Thumbnails

1280×720 PNG for YouTube. Generate candidates by extracting the strongest
frames, then composite title text:

```bash
ffmpeg -ss 00:00:12 -i out/demo-16x9.mp4 -frames:v 1 -q:v 2 thumb-raw.png
```

Overlay 3–5-word title text (large, high-contrast, safe margins) via an
HTML page screenshotted with Playwright, or ImageMagick. Offer the user
2–3 candidates.

## Upload

Manual by default. If the user asks for automation:

- **YouTube**: YouTube Data API v3 (`videos.insert`, then
  `thumbnails.set`) — needs OAuth; quota cost per upload is significant.
- **TikTok / IG / LinkedIn / X**: APIs are restricted or app-review-gated;
  assume manual upload unless the user already has API access.

(These API notes are general knowledge — research had no verified claims
here; verify current API terms before building automation.)

## Delivery checklist

- [ ] Files named `<name>-<aspect>.mp4`, plus `.srt` and thumbnail
- [ ] Each file opens and plays (spot-check first/last seconds)
- [ ] User approved the master in Phase 6 QA
- [ ] Per-platform copy drafted if asked (title, description, hashtags)
- [ ] User explicitly approved any actual upload/post
