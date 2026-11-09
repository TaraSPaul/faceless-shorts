---
name: faceless-shorts
description: Make narrated faceless YouTube Shorts / TikToks / Reels fully in code on the user's computer, with a free local neural AI voice (Kokoro-82M, human-like 21yo Hindi female hf_beta) and word-synced captions, $0. Follows a strict 3-step workflow: 1. Script First -> 2. Video Creation -> 3. Title, Description & Trending Hashtags (in English only). Six styles - Deep Dive 3D (Zack D. Films-like 3D explainers), Night File 3D (unsolved mysteries, true crime), Inside Out (flat 2D x-ray explainers), Stick Story (survival steps), Paper Atlas (history cut paper maps), Tall Tale 3D (funny true stories).
---

# Faceless Shorts

You make a finished vertical short from a topic: script, voice, word-synced captions, animated shots, sound and
music, rendered to MP4. **Everything is code**: canvas drawing, headless Chrome capture, ffmpeg, local Kokoro neural voice,
local Whisper/exact word timing, numpy sound. No AI images or video, no API keys, no credits.
`SKILL` = the folder this file is in. Projects live in `~/faceless-shorts/<short-name>/`.

| style | what it makes | length · aspect |
|---|---|---|
| **Deep Dive 3D** `deep-dive` | the flagship, Zack D. Films-like: sculpted 3D people in sunlit sets, glowing x-ray bodies, camera journeys through blood vessels, shallow focus. "What happens if…?" body and science | 30-45 s · 9:16 |
| **Night File 3D** `night-file` | unsolved mysteries / true crime: dark 3D places with one light, faceless people (the subject glows red), typewriter dates, case-file inserts | 30-45 s · 9:16 |
| **Inside Out** `inside-out` | flat 2D "What happens if…?" explainer: a simple hero, x-ray cutaways, bold 1-3 word captions, punchy cuts | 20-35 s · 9:16 |
| **Stick Story** `stick-story` | "What would you do if…?" survival steps: stick people with acting eyes, flat rooms day/night, gold step cards | 30-45 s · 9:16 |
| **Paper Atlas** `paper-atlas` | history in cut paper: parchment maps, crimson routes, gold date ribbons, period figures | 30-45 s · 9:16 |
| **Tall Tale 3D** `tall-tale` | funny true stories: flat 2D cartoon people (big round heads, ink outlines) acting in a sunny 3D small-town world, camera always moving, one-word captions | 40-60 s · 9:16 |

Which style: body / health / science / tech "what happens if" → **Inside Out** (clean, fast 2D canvas, ultra reliable) or **Deep Dive 3D** · creepy, unexplained, true crime → **Night File 3D** · survival, life hacks → **Stick Story** · historical events → **Paper Atlas** · funny or clever true stories → **Tall Tale 3D**.

---

## 🔒 MANDATORY 3-PHASE CREATION WORKFLOW

Every time a video is requested, you MUST strictly follow this 3-phase order:

### Phase 1: Script & Plan First
1. Write the conversational script before rendering any video:
   - **Narration Language**: Hindi (default) using natural conversational phrasing.
   - **Voice**: 21-year-old female (`hf_beta`, Kokoro-82M).
   - **Pacing**: ~45-55 words for 20s; ~70-90 words for 30s; ~115-135 words for 45s.
   - **Structure**: Hook (0-4s) → Build Curiosity (4-10s) → Twist/Climax (10-16s) → Punchy Call to Action (16-20s).
   - **Cuts**: One line per cut (1.5 - 3.2 seconds each).
   - **Captions**: Format with `caps` chunks and `*` for the single yellow keyword (e.g., `POORI HUMAN *RACE | SUGAR *CUBE`).
2. Show the complete script, shot list, and sources to the user.

### Phase 2: Video & Audio Creation
1. Copy style files to project: `bash SKILL/scripts/new_video.sh <style> <short-name>`.
2. Write `script.json` with the timed lines, `"voice": "hf_beta"`, and `"lang": "hi"`.
3. **Voiceover**: Generate natural neural narration using Kokoro-82M Hindi female voice (`voice: "hf_beta"`, 21 years old).
   - **VOICE QUALITY RULE**: Always use Kokoro neural voices for realistic human warmth, natural breaths, and 21yo female inflection. **Never use robotic legacy SAPI5 voices.**
4. Timing & Alignment: Generate `lines.json`, `data/narration.wav`, and `words.json`.
5. Animate `src/shots.js`:
   - Quick cuts every 2–3 seconds.
   - **SAFE ZONE & COLLISION RULE**: All visual characters, cards, and arrows MUST stay in the upper-middle zone ($y = 300 - 950$).
   - **COMMENT BELOW / CTA RULE**: The lower third ($y = 1100 - 1550$) is strictly reserved for the $150\text{px}$ bold subtitles (e.g. `COMMENT *KAREIN`). Never draw visual cards, arrows, or props in this lower-third zone to prevent any overlapping or obscured text.
6. Build audio mix: `node tools/capture.mjs cues` → `python tools/mix.py .` (procedural music bed + whooshes/slams/pops).
7. QA review: `node tools/capture.mjs sheet review/all.jpg 1 8` and review keyframes.
8. Render vertical MP4: `node tools/capture.mjs video renders/<name>.mp4` (1080x1920 @ 30 FPS).

### Phase 3: Metadata & Viral Publishing Package (ENGLISH ONLY)
Immediately after rendering the video, generate and deliver:
1. **Click-Worthy Video Title**: High-CTR viral title with relevant emoji — **MUST BE IN ENGLISH ONLY** (e.g. `Physics Facts That Break Reality 🤯`).
2. **Engaging Video Description**: Clear 2-3 sentence overview ending with `#shorts` — **MUST BE IN ENGLISH ONLY**.
3. **Trending Hashtags**: 5–8 targeted hashtags — **MUST BE IN ENGLISH ONLY** (e.g. `#Shorts #Physics #ScienceFacts #QuantumPhysics #MindBlowing`).
4. **Thumbnail Cover Frame**: Key moment extracted with `capture.mjs frames`.

---

## 4. QA Checklist (Verify before delivery)
- **Voiceover**: Natural human-like neural cadence in Hindi (Kokoro `hf_beta`, 21yo female), clear over music, zero robotic artifacts.
- **Captions**: 1–3 words, exactly one yellow word, synced to speech, bold & high-contrast, readable on mobile.
- **Metadata**: Title, Description, and Hashtags **MUST BE IN ENGLISH ONLY**.
- **Lower Third Clearance**: Zero visual elements colliding with subtitles at $y = 1100 - 1550$.
- **Call-to-Action**: "Comment karein / Comment below" card clearly visible above $y = 950$, with unobstructed subtitle below it.
- **Format**: Vertical 9:16 (1080×1920), 30 fps, crisp MP4 encoding.

---

## 5. Publishing to YouTube
- Use YouTube Studio direct upload with profile pre-selection, or
- Automated upload script via YouTube Data API v3 (`upload_to_youtube.py`), or
- Automated Zapier webhook with temporary hosted link (`litterbox` / `uguu.se`).
