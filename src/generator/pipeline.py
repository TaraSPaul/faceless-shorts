"""
generator/pipeline.py — Video generation pipeline orchestrator.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import boto3
import requests
from core import config, s3

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_DIR = BASE_DIR / "styles"
SCRIPTS_DIR = BASE_DIR / "scripts"
WORKSPACE_DIR = Path(os.environ.get("SHORTS_WORKSPACE", "/tmp/shorts" if os.name != 'nt' else "C:/tmp/shorts"))
SCENE_MODEL_ID = os.environ.get("SCENE_MODEL_ID", "us.amazon.nova-pro-v1:0")


def _generate_cut_queries(topic: str, lines: list) -> list[str]:
    """Use Amazon Bedrock to choose specific, concrete Wikipedia/Wikimedia visual search queries per cut."""
    if not lines:
        return [topic]

    cuts_summary = "\n".join(
        f"Cut {i}: {ln.get('text', '')!r} (badge: {ln.get('caps', '')!r})"
        for i, ln in enumerate(lines)
    )
    prompt = f"""You are a video editor sourcing a DIFFERENT real photograph for EVERY cut of a vertical explainer short about:
"{topic}"

Cuts:
{cuts_summary}

CRITICAL RULES FOR SEARCH QUERIES:
1. Every query MUST be explicitly grounded in the physical domain of "{topic}" (e.g., if the topic is about airplane windows, EVERY query must mention aircraft/airplane/aviation/cabin/sky; if about car tires/doors, EVERY query must mention car/automobile/tire/wheel/engine).
2. NEVER write generic or abstract phrases like "Small hole", "Pressure balance", "Pressure imbalance", "Hook question", or "Call to action" — Wikipedia will return black holes or biology diagrams!
3. Use 2–3 word concrete English Wikipedia article titles / photo subjects that are distinct across cuts.
   Example for "Why Do Airplane Windows Have a Tiny Hole?":
   ["Aircraft cabin window", "Commercial airliner sky", "Aircraft cabin seats", "Poly(methyl methacrylate)", "Cockpit instruments", "Aircraft wing clouds", "Boeing 787 window", "Commercial aviation sunset"]
   Example for "Why Do Luxury Cars Have Soft-Close Doors?":
   ["Luxury car exterior", "Car door handle", "Electric motor actuator", "Automobile assembly", "Luxury car interior", "Car dashboard night", "Sports sedan parked"]

Return ONLY a JSON array of {len(lines)} concrete, domain-anchored English search queries (no markdown fences)."""

    try:
        br = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        resp = br.converse(
            modelId=SCENE_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 600, "temperature": 0.4},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            raw = m.group(0)
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            queries = [str(q).strip() or topic for q in parsed[:len(lines)]]
            while len(queries) < len(lines):
                queries.append(topic)
            return queries
    except Exception as exc:
        logger.warning(f"Bedrock query generation failed ({exc}); deriving keyword queries.")

    # Keyword fallback per cut
    out = []
    for ln in lines:
        words = re.findall(r"[A-Za-z]{3,}", (ln.get("caps") or "") + " " + topic)
        out.append(" ".join(words[:3]) if words else topic)
    return out


def _fetch_episodic_images(topic: str, lines: list, project_dir: Path) -> int:
    """Fetch a distinct high-resolution photo for every cut via Wikipedia & Wikimedia Commons."""
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not lines:
        return 0

    queries = _generate_cut_queries(topic, lines)
    logger.info(f"Episodic visual queries: {queries}")

    session = requests.Session()
    session.headers.update({"User-Agent": "FacelessShortsStudio/1.0 (https://github.com/TaraSPaul/faceless-shorts)"})

    def search_candidates(q: str) -> list[str]:
        urls = []
        try:
            r = session.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query",
                "generator": "search",
                "gsrsearch": q,
                "gsrlimit": 6,
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": 1080,
                "format": "json"
            }, timeout=8).json()
            for p in sorted(r.get("query", {}).get("pages", {}).values(), key=lambda x: x.get("index", 99)):
                src = p.get("thumbnail", {}).get("source", "")
                if src and not src.lower().endswith((".svg", ".gif")):
                    urls.append(src)
        except Exception:
            pass

        try:
            r2 = session.get("https://commons.wikimedia.org/w/api.php", params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{q} filetype:bitmap",
                "gsrnamespace": "6",
                "gsrlimit": 6,
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": "1080",
                "format": "json"
            }, timeout=8).json()
            for p in r2.get("query", {}).get("pages", {}).values():
                info = (p.get("imageinfo") or [{}])[0]
                src = info.get("thumburl") or info.get("url", "")
                if info.get("mime") in ("image/jpeg", "image/png") and src:
                    urls.append(src)
        except Exception:
            pass
        return urls

    with ThreadPoolExecutor(max_workers=8) as ex:
        all_candidates = list(ex.map(search_candidates, queries))

    # Also grab fallback pool from the main topic
    topic_pool = search_candidates(topic)

    # Assign a unique image URL per cut so cuts don't repeat photos
    used_urls = set()
    chosen = []
    for idx, cands in enumerate(all_candidates):
        pick = None
        for u in cands + topic_pool:
            if u not in used_urls:
                pick = u
                used_urls.add(u)
                break
        if not pick and cands:
            pick = cands[0]
        elif not pick and topic_pool:
            pick = topic_pool[idx % len(topic_pool)]
        chosen.append((idx, pick))

    def download_one(item):
        idx, url = item
        if not url:
            return False
        try:
            r = session.get(url, timeout=10)
            if r.status_code == 200 and len(r.content) > 8000:
                ext = "png" if "png" in r.headers.get("Content-Type", "").lower() else "jpg"
                (data_dir / f"bg_{idx}.{ext}").write_bytes(r.content)
                return True
        except Exception:
            pass
        return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(download_one, chosen))

    count = sum(1 for ok in results if ok)
    logger.info(f"Downloaded {count}/{len(lines)} unique episodic photos.")
    return count


def _build_default_shots_js(topic: str, lines: list) -> str:
    """Generate dynamic Ken Burns + animated HUD overlay shots.js using unique episodic visuals."""
    badges = []
    for i, ln in enumerate(lines):
        caps = (ln.get("caps") or "").replace("*", "").split("|")[0].strip()
        label = (caps or topic)[:26].replace("'", "\\'").replace('"', '\\"')
        badges.append(label)

    badges_js = json.dumps(badges, ensure_ascii=False)
    topic_esc = topic[:32].replace('"', '\\"')

    return f"""// Dynamic episodic motion graphics + Ken Burns photography shots.js
import {{ ctx, C, W, H, clamp, lerp, seg, eo, eio, eob, rnd, bigText, rr, circle, line }} from './core/lib.js';
import {{ L, Le, T }} from './core/timing.js';
import * as K from './core/kit.js';

const BADGES = {badges_js};

function drawCover(img, cx, cy, boxW, boxH, zoom, panX, panY) {{
  const arImg = img.width / img.height;
  const arBox = boxW / boxH;
  let dw, dh;
  if (arImg > arBox) {{
    dh = boxH * zoom;
    dw = dh * arImg;
  }} else {{
    dw = boxW * zoom;
    dh = dw / arImg;
  }}
  ctx.drawImage(img, cx - dw / 2 + panX, cy - dh / 2 + panY, dw, dh);
}}

export function buildShots() {{
  const S = [], CUES = [];
  const add = (o) => (S.push(o), o);
  const cue = (t, type, o = {{}}) => CUES.push({{ t: +t.toFixed(3), type, ...o }});
  const cut = (i) => (i === 0 ? 0 : L(i) - 0.08);
  const BGS = globalThis.__FAC_BGS__ || [];

  const count = T.lines.length;
  for (let i = 0; i < count; i++) {{
    const st = cut(i);
    const badge = BADGES[i] || "{topic_esc}";
    const isAlt = i % 2 === 1;
    const isLast = i === count - 1;
    const motionMode = i % 4;

    add({{
      id: 'S' + String(i + 1).padStart(2, '0'),
      at: st,
      cam: [540, 560],
      zoom: 0.025,
      note: 'Episodic dynamic scene ' + i + ': ' + badge,
      draw(lt, d, t) {{
        const p = clamp(lt / Math.max(0.5, d));

        // 1. Deep dark studio backdrop
        ctx.fillStyle = '#070B14';
        ctx.fillRect(-200, -200, W + 400, H + 400);

        const bg = BGS[i] || BGS.find(Boolean);
        if (bg) {{
          // Alternating Ken Burns camera choreography per cut
          let zoom = 1.08;
          let panX = 0;
          let panY = 0;
          if (motionMode === 0) {{
            zoom = lerp(1.02, 1.18, eio(p));
            panY = lerp(25, -25, p);
          }} else if (motionMode === 1) {{
            zoom = lerp(1.18, 1.04, eio(p));
            panX = lerp(-45, 45, p);
          }} else if (motionMode === 2) {{
            zoom = lerp(1.05, 1.16, eio(p));
            panX = lerp(45, -45, p);
          }} else {{
            zoom = lerp(1.15, 1.02, eio(p));
            panY = lerp(-30, 30, p);
          }}

          // Rounded full-width cinematic viewport (y = 140 .. 1010, completely clear of captions)
          ctx.save();
          rr(48, 160, 984, 830, 38);
          ctx.clip();
          drawCover(bg, 540, 575, 984, 830, zoom, panX, panY);

          // Cinematic top/bottom vignette inside card
          const grad = ctx.createLinearGradient(0, 160, 0, 990);
          grad.addColorStop(0, 'rgba(7, 11, 20, 0.55)');
          grad.addColorStop(0.25, 'rgba(7, 11, 20, 0.0)');
          grad.addColorStop(0.75, 'rgba(7, 11, 20, 0.05)');
          grad.addColorStop(1, 'rgba(7, 11, 20, 0.72)');
          ctx.fillStyle = grad;
          ctx.fillRect(48, 160, 984, 830);
          ctx.restore();

          // Glowing outer border around viewport
          ctx.strokeStyle = isLast ? '#FACC15' : (isAlt ? '#38BDF8' : '#FFFFFF');
          ctx.lineWidth = 6;
          rr(48, 160, 984, 830, 38);
          ctx.stroke();

          // Dynamic pulsing focus reticle highlighting focal zone
          const rx = 540 + Math.sin(lt * 1.4 + i) * 140;
          const ry = 560 + Math.cos(lt * 1.1 + i) * 70;
          const pr = 56 + Math.sin(lt * 6) * 8;
          ctx.save();
          ctx.strokeStyle = isAlt ? 'rgba(56, 189, 248, 0.7)' : 'rgba(250, 204, 21, 0.75)';
          ctx.lineWidth = 5;
          ctx.beginPath();
          ctx.arc(rx, ry, pr, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }} else {{
          K.xray(t);
        }}

        // 2. Top Story Progress Bar across all cuts (y = 104)
        ctx.fillStyle = 'rgba(255,255,255,0.18)';
        rr(64, 104, 952, 12, 6);
        ctx.fill();
        const totalPct = clamp(t / Math.max(0.5, T.dur));
        ctx.fillStyle = '#38BDF8';
        rr(64, 104, Math.max(18, 952 * totalPct), 12, 6);
        ctx.fill();

        // 3. Animated Top Episodic Badge Pill (crisp clean typography, no smeared outline)
        const slide = eo(seg(lt, 0.0, 0.28));
        const bx = lerp(-240, 82, slide);
        ctx.save();
        ctx.translate(bx, 198);
        ctx.fillStyle = isLast ? '#FACC15' : '#0F172A';
        ctx.strokeStyle = isLast ? '#0F172A' : '#38BDF8';
        ctx.lineWidth = 4;
        rr(0, 0, 560, 68, 20);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = isLast ? '#0F172A' : '#FACC15';
        ctx.font = '900 28px Inter';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText('0' + (i + 1) + '  ·  ' + badge.toUpperCase(), 26, 35);
        ctx.restore();

        // 4. Expressive mini host reaction in corner above caption safe zone
        K.man({{
          x: 910,
          y: 895,
          s: 0.28,
          xray: false,
          arm: isLast ? K.ARM.wave : (isAlt ? K.ARM.point : K.ARM.hip),
          mouth: Math.sin(lt * 12) > 0 ? 'o' : (isLast ? 'grin' : 'smile'),
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

    # 2b. Fetch unique episodic photos per cut (unless caller passed custom shots_js)
    custom_shots_js = payload.get("shots_js")
    if not custom_shots_js:
        _fetch_episodic_images(topic, script_data.get("lines", []), project_dir)
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
