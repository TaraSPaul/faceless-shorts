"""
generator/pipeline.py — Video generation pipeline orchestrator.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import boto3
from core import config, s3

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_DIR = BASE_DIR / "styles"
SCRIPTS_DIR = BASE_DIR / "scripts"
WORKSPACE_DIR = Path(os.environ.get("SHORTS_WORKSPACE", "/tmp/shorts" if os.name != 'nt' else "C:/tmp/shorts"))
SCENE_MODEL_ID = os.environ.get("SCENE_MODEL_ID", "us.amazon.nova-lite-v1:0")


def _generate_episodic_svgs(topic: str, lines: list, project_dir: Path) -> list[str]:
    """Generate a unique flat-vector SVG illustration per script cut via Amazon Bedrock."""
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not lines:
        return []

    cuts_summary = "\n".join(
        f"Cut {i}: spoken={ln.get('text', '')!r}, headline={ln.get('caps', '')!r}"
        for i, ln in enumerate(lines)
    )
    prompt = f"""You are a motion graphics art director creating unique episodic vector illustrations for each scene cut of a vertical YouTube Short about: "{topic}".

Here are the {len(lines)} cuts:
{cuts_summary}

Generate exactly {len(lines)} DISTINCT flat-vector SVG illustrations (one for each cut, visually showing what happens in THAT specific cut — do NOT repeat the same object across cuts).
Strict SVG rules:
- Each item must be a valid SVG string starting with `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 320">` and ending with `</svg>`.
- Draw crisp, recognizable multi-part scenes using geometric primitives (<rect>, <circle>, <ellipse>, <polygon>, <path>, <line>) with rich contrasting colors (#0F172A, #1E293B, #334155, #38BDF8, #FACC15, #F43F5E, #22C55E, #FFFFFF, #CBD5E1).
- NEVER use <text>, <style>, <script>, <image>, or external URLs.
- Keep main artwork centered well inside x=40..380, y=30..290.

Return ONLY a JSON array of {len(lines)} SVG strings (no markdown fences)."""

    svgs = []
    try:
        br = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        resp = br.converse(
            modelId=SCENE_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 4096, "temperature": 0.65},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
        # Extract JSON array cleanly if any prose wraps it
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            raw = m.group(0)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            for idx, item in enumerate(parsed[:len(lines)]):
                if isinstance(item, str) and "<svg" in item and "</svg>" in item:
                    svg_clean = item[item.index("<svg"):item.rindex("</svg>") + 6]
                    (data_dir / f"illus_{idx}.svg").write_text(svg_clean, encoding="utf-8")
                    svgs.append(svg_clean)
        logger.info(f"Generated {len(svgs)}/{len(lines)} episodic SVG scenes via Bedrock ({SCENE_MODEL_ID}).")
    except Exception as exc:
        logger.warning(f"Bedrock episodic SVG generation skipped/partial ({exc}); using procedural shapes fallback.")
    return svgs


def _build_default_shots_js(topic: str, lines: list) -> str:
    """Generate a safe-zone compliant, episodic shots.js displaying each cut's SVG illustration."""
    badges = []
    for i, ln in enumerate(lines):
        caps = (ln.get("caps") or "").replace("*", "").split("|")[0].strip()
        label = (caps or topic)[:22].replace("'", "\\'").replace('"', '\\"')
        badges.append(label)

    badges_js = json.dumps(badges, ensure_ascii=False)
    topic_esc = topic[:28].replace('"', '\\"')

    return f"""// Auto-generated episodic safe-zone shots.js
import {{ ctx, C, W, H, clamp, lerp, seg, eo, eio, eob, rnd, bigText, rr, circle, line }} from './core/lib.js';
import {{ L, Le, T }} from './core/timing.js';
import * as K from './core/kit.js';

const BADGES = {badges_js};

export function buildShots() {{
  const S = [], CUES = [];
  const add = (o) => (S.push(o), o);
  const cue = (t, type, o = {{}}) => CUES.push({{ t: +t.toFixed(3), type, ...o }});
  const cut = (i) => (i === 0 ? 0 : L(i) - 0.08);
  const ILLUS = globalThis.__FAC_ILLUS__ || [];

  const count = T.lines.length;
  for (let i = 0; i < count; i++) {{
    const st = cut(i);
    const badge = BADGES[i] || "{topic_esc}";
    const isAlt = i % 2 === 1;
    const isLast = i === count - 1;

    add({{
      id: 'S' + String(i + 1).padStart(2, '0'),
      at: st,
      cam: [540, 620],
      zoom: 0.03 + 0.015 * (i % 3),
      note: 'Episodic scene ' + i + ': ' + badge,
      draw(lt, d, t) {{
        if (isAlt) {{
          K.xray(t);
        }} else {{
          K.room();
        }}

        const pop = eob(seg(lt, 0.05, 0.35));
        const bob = Math.sin(lt * 2.4 + i * 1.1) * 9;

        // 1. Top cut headline pill (y = 215..305)
        ctx.save();
        ctx.translate(540, 260);
        ctx.scale(pop, pop);
        ctx.fillStyle = isLast ? C.red : (isAlt ? C.navy : C.white);
        ctx.strokeStyle = isAlt ? C.cyan : C.ink;
        ctx.lineWidth = 7;
        rr(-350, -45, 700, 90, 26);
        ctx.fill();
        ctx.stroke();
        bigText(badge.toUpperCase(), 0, 2, 36, isLast ? C.white : (isAlt ? C.yellow : C.navy), 0, 1);
        ctx.restore();

        // 2. Main Episodic Illustration Stage Card (y = 330..870)
        ctx.save();
        ctx.translate(500, 600 + bob);
        ctx.scale(pop, pop);

        ctx.fillStyle = isAlt ? '#0F172A' : '#FFFFFF';
        ctx.strokeStyle = isAlt ? C.cyan : C.ink;
        ctx.lineWidth = 8;
        rr(-360, -250, 720, 500, 36);
        ctx.fill();
        ctx.stroke();

        const ill = ILLUS[i] || ILLUS[i % Math.max(1, ILLUS.length)];
        if (ill) {{
          const pulse = 1 + 0.035 * Math.sin(lt * 3.0);
          ctx.save();
          ctx.scale(pulse, pulse);
          ctx.drawImage(ill, -330, -225, 660, 450);
          ctx.restore();
        }} else {{
          // Procedural fallback shapes varied per cut index
          const phase = lt * 2.5 + i;
          circle(0, 0, 140 + Math.sin(phase) * 12, isAlt ? C.cyan : C.yellow);
          circle(0, 0, 88, isAlt ? C.navy : C.red);
          bigText('#' + (i + 1), 0, 4, 84, C.white, 0, 1);
        }}
        ctx.restore();

        // 3. Compact expressive presenter cleanly in right upper-mid safe zone (y = 660..1040)
        K.man({{
          x: 915,
          y: 840,
          s: 0.34,
          xray: isAlt,
          arm: isLast ? K.ARM.wave : (isAlt ? K.ARM.point : K.ARM.hip),
          mouth: Math.sin(lt * 11) > 0 ? 'o' : (isLast ? 'grin' : 'smile'),
          eyes: isLast ? 'wide' : 'n',
          brow: isLast ? 1 : 0
        }});
      }}
    }});

    cue(st, i === 0 ? 'pop' : 'whoosh', {{ gain: 0.55 }});
    if (isLast) cue(st + 0.25, 'sparkle', {{ gain: 0.65 }});
  }}

  return {{ shots: S, cues: CUES }};
}}
"""


def run_cmd(cmd, cwd=None):
    logger.info(f"Running: {' '.join(str(c) for c in cmd)} (cwd={cwd})")
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"Command failed ({res.returncode}):\n{res.stderr}")
        raise RuntimeError(f"Command failed: {res.stderr or res.stdout}")
    return res.stdout


def generate_short(payload: dict) -> dict:
    """
    Generate vertical video short from payload and upload to S3.
    """
    topic = payload.get("topic", "Interesting Facts")
    style = payload.get("style", config.DEFAULT_STYLE)
    voice = payload.get("voice", config.DEFAULT_VOICE)
    lang = payload.get("lang", config.DEFAULT_LANG)
    script_data = payload.get("script")

    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:30] or "short-video"
    project_dir = WORKSPACE_DIR / slug
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy style template
    src_example = STYLES_DIR / style / "example"
    if not src_example.exists():
        src_example = STYLES_DIR / "inside-out" / "example"
    for item in src_example.iterdir():
        if item.is_dir():
            shutil.copytree(item, project_dir / item.name)
        else:
            shutil.copy2(item, project_dir / item.name)

    # 2. Write script.json
    if not script_data:
        script_data = {
            "title": topic,
            "voice": voice,
            "engine": "elevenlabs" if voice.startswith("elevenlabs:") else ("edge" if voice.endswith("Neural") else "kokoro"),
            "lang": lang,
            "speed": 1.05,
            "lead": 0.45,
            "outro": 0.9,
            "gap": 0.32,
            "music": "bed",
            "sources": ["General Verified Knowledge"],
            "lines": payload.get("lines", [
                {"text": f"क्या आपको पता है {topic} के बारे में?", "caps": "FACT CHECK | DID YOU *KNOW?"},
                {"text": "यह सच जानकर आप हैरान रह जाएंगे!", "caps": "SHOCKING *TRUTH | MUST *WATCH"},
                {"text": "अगली बार किसी को यह बात ज़रूर बताएं और नीचे कमेंट करें!", "caps": "SHARE *THIS | COMMENT *KAREIN"}
            ])
        }
    else:
        script_data["voice"] = voice
        script_data["lang"] = lang
        script_data["engine"] = "elevenlabs" if voice.startswith("elevenlabs:") else ("edge" if voice.endswith("Neural") else "kokoro")

    (project_dir / "script.json").write_text(json.dumps(script_data, indent=1, ensure_ascii=False), encoding="utf-8")

    # 2b. Generate unique episodic SVG scenes per cut (unless caller passed custom shots_js)
    custom_shots_js = payload.get("shots_js")
    if not custom_shots_js:
        _generate_episodic_svgs(topic, script_data.get("lines", []), project_dir)
        shots_js_content = _build_default_shots_js(topic, script_data.get("lines", []))
    else:
        shots_js_content = custom_shots_js
    (project_dir / "src/shots.js").write_text(shots_js_content, encoding="utf-8")

    # 3. Synthesize voice
    logger.info(f"Synthesizing voice ({voice})...")
    run_cmd([sys.executable, str(SCRIPTS_DIR / "voice.py"), str(project_dir)])

    # 4. Align words
    logger.info("Aligning words...")
    run_cmd([sys.executable, str(SCRIPTS_DIR / "words.py"), str(project_dir)])

    # 5. Extract cues, mix audio, and render MP4 + thumbnail
    mp4_name = f"{slug}.mp4"
    renders_dir = project_dir / "renders"
    renders_dir.mkdir(exist_ok=True)
    mp4_path = renders_dir / mp4_name
    thumb_path = project_dir / "review/frames/t2.00.jpg"
    fast_renderer = SCRIPTS_DIR / "render_fast.mjs"

    can_use_fast = (
        style == "inside-out"
        and fast_renderer.exists()
        and "document." not in shots_js_content
        and "window." not in shots_js_content
    )

    if can_use_fast:
        logger.info("Extracting sound cues (fast native Skia path)...")
        run_cmd(["node", str(fast_renderer), "cues", str(project_dir)], cwd=project_dir)
        run_cmd([sys.executable, "tools/mix.py", "."], cwd=project_dir)
        logger.info(f"Rendering video + thumbnail cleanly via render_fast.mjs -> {mp4_path}...")
        run_cmd(["node", str(fast_renderer), "video", f"renders/{mp4_name}", str(project_dir)], cwd=project_dir)
    else:
        logger.info("Extracting sound cues & mixing audio (Chromium path)...")
        run_cmd(["node", "tools/capture.mjs", "cues"], cwd=project_dir)
        run_cmd([sys.executable, "tools/mix.py", "."], cwd=project_dir)
        logger.info(f"Rendering video to {mp4_path}...")
        run_cmd(["node", "tools/capture.mjs", "video", f"renders/{mp4_name}"], cwd=project_dir)
        # Extract thumbnail directly via ffmpeg instead of spawning Chrome again
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        run_cmd(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", str(mp4_path), "-frames:v", "1", "-q:v", "2", str(thumb_path)])

    # 6. Upload to S3
    logger.info("Uploading assets to S3...")
    s3_info = s3.upload_video_package(mp4_path, thumb_path, project_name=slug)

    # 7. Format English Publishing Package
    title = f"{topic} 🚗✨ #Shorts"
    description = f"Discover the surprising facts behind {topic}! Narrated with hyperrealistic AI voice and English subtitles. Subscribe for more amazing daily facts! #shorts"
    hashtags = ["#Shorts", "#DailyFacts", "#DidYouKnow", "#FactCheck", "#ViralShorts", "#MindBlowing"]

    return {
        "status": "success",
        "topic": topic,
        "style": style,
        "voice": voice,
        "video_url": s3_info["video_download_url"],
        "video_s3_key": s3_info["video_s3_key"],
        "thumbnail_url": s3_info["thumbnail_url"],
        "metadata": {
            "title": title,
            "description": description,
            "hashtags": hashtags
        }
    }
