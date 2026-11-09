# Inside Out: flat 2D "What happens if…?" shorts, 9:16

Curious, slightly shocking, satisfying. A simple flat hero, x-ray cutaways into the body, organs and props as clean
vector shapes, bold 1-3 word captions with one yellow word, and a cut every 1-3 seconds with the camera always moving.
Example to study and copy: `example/` = **WHAT IF YOU SWALLOW GUM?** (30 s, 11 shots). Style sheet: `style-sheet.png`.

## 1. The look (rules from the sheet: do not break them)
- **Flat shapes only.** No gradients, textures or realistic lighting. Depth comes from flat darker/lighter tones of the
  same colour (shirt shade, organ highlight), never from blur or glow.
- **Palette:** skin `#E8B89A` · organ pink `#E57A8A` · danger red `#D62839` · x-ray cyan `#4FD1E8` · highlight yellow
  `#FFD43B` · background `#F4F1EA`, plus ink `#1A1A1E` and the derived shades in `lib.js` `C`.
- **X-ray cyan is only for inside-the-body views** (skeleton, x-ray film background, gut glow). **Red marks danger or the
  problem** (X, warning, blockage ring, stopwatch hand). **Yellow is the one keyword per caption**, impact bursts and acid.
- **One visual mode per shot.** X-ray means the whole body is x-ray (arms, neck, legs), only the head stays normal.
- Characters are minimal and friendly: round head, dot eyes with a highlight, simple tee and pants, expressive brows and
  mouth. They react on the beat (gulp, shock, smirk, finger wag) and may look at the camera on the twist ending.
- Mood: curious, slightly shocking, satisfying. Accurate science, no gore, no injury on screen.

## 2. Format
- **1080x1920, 30 fps, 25-45 s.** Lead silence 0.45 s, outro 0.9 s (they're in `script.json`).
- **Story shape:** hook question (hero + the thing) → x-ray: where it goes → close-up of what happens → the key fact →
  myth busted (red X) → what really happens → time passes → **twist: "but if you…"** (danger, red) → the hero's punchy
  last line to camera (loops back to the hook).
- **One line = one shot = one cut**, and a sentence usually spans 2-3 lines.
  Shots are 1.5-3.5 s; split a line that runs longer. Every cut gets a punch-in + a brief
  white flash + a whoosh (automatic in `main.js`; add the whoosh cue yourself).
- **Narration:** conversational Hindi, like explaining to a friend: flowing sentences with connecting words, never a list of
  caption-like fragments. Kokoro `hf_beta (Hindi female, age 21)` x1.0 (or `hf_alpha` for calm female, `af_bella` for English). Calm, curious,
  matter-of-fact. Numbers spelled as said.

## 3. Captions
`script.json` line: `{ "text": "Stuck for seven years? Total myth.", "caps": "STUCK 7 *YEARS? | TOTAL *MYTH" }`
- `|` splits the line into caption chunks; `*` marks the ONE yellow word of each chunk. 1-3 words per chunk.
- A chunk appears when its first word is spoken (matched by spelling, else by word count), pops in (0.2 s overshoot), and
  stays until the next chunk. Inter Black 150 px, white, ink outline 30 px + drop, centred at y 1400 (`CAP` in captions.js).
- Caps may differ from the spoken words ("7" for "seven") but should start with the same word as the spoken chunk.
- Without `caps`, lines are auto-chunked (2-3 words, longest word yellow): fine for drafts, write caps for the final.

## 4. Engine map (`example/`)
| file | gives you |
|---|---|
| `script.json` | title, voice, speed, lead, outro, gap, music (`bed`·`none`·`audio/x.mp3`), sources, lines `{text, caps, gap}` |
| `src/shots.js` | **the per-video file**: the shot list + sound cues |
| `src/core/kit.js` | the component zoo (below) |
| `src/core/lib.js` | `W H FPS`, palette `C`, `clamp lerp seg eo eio eob rnd`, `rr circle ell line fillAll bigText` |
| `src/core/timing.js` | `L(i)` line start, `Le(i)` line end, `Wd(word, line)` word start (prefix match, throws if missing), `T.dur` |
| `src/core/captions.js` | caption chunking + drawing (`CAP` = position/size) |
| `src/main.js` | boot, camera (punch-in + slow push), cut flash, fades, `window.OP` for capture |
| `tools/capture.mjs` | `check` · `cues` · `sheet` · `frames` · `video [start end] [--draft]` · `preview` |
| `tools/mix.py` | voice + music bed (ducked) + procedural effects → `data/mix.wav` |
| `data/` | `lines.json`, `words.json` (timing), `narration.wav`, `cues.json`, `mix.wav` |

## 5. Safe Zones & Layout Rules
- Keep all visual action, characters, cards, and arrows strictly between y 300 and y 950.
- Never draw graphics, cards, or arrows in the lower third (y 1100-1550). That zone is strictly reserved for subtitles (e.g. COMMENT *KAREIN at y 1400) to prevent any overlapping text.
- Voiceover must use Kokoro-82M neural model (hf_beta, Hindi female, age 21) for human-like narration; never use robotic system voices.
