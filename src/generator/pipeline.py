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
from core import config, s3

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_DIR = BASE_DIR / "styles"
SCRIPTS_DIR = BASE_DIR / "scripts"
WORKSPACE_DIR = Path(os.environ.get("SHORTS_WORKSPACE", "/tmp/shorts" if os.name != 'nt' else "C:/tmp/shorts"))

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
        # Default fallback lines if script wasn't explicitly passed
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

    # 3. Synthesize voice
    logger.info(f"Synthesizing voice ({voice})...")
    voice_script = SCRIPTS_DIR / "voice.py"
    run_cmd([sys.executable, str(voice_script), str(project_dir)])

    # 4. Align words
    logger.info("Aligning words...")
    words_script = SCRIPTS_DIR / "words.py"
    run_cmd([sys.executable, str(words_script), str(project_dir)])

    # 5. Extract cues & audio mix
    logger.info("Extracting sound cues & mixing audio...")
    run_cmd(["node", "tools/capture.mjs", "cues"], cwd=project_dir)
    run_cmd([sys.executable, "tools/mix.py", "."], cwd=project_dir)

    # 6. Capture thumbnail frame
    logger.info("Capturing thumbnail frame...")
    run_cmd(["node", "tools/capture.mjs", "frames", "review/frames", "2.0"], cwd=project_dir)
    thumb_path = project_dir / "review/frames/t2.00.jpg"

    # 7. Render MP4
    mp4_name = f"{slug}.mp4"
    renders_dir = project_dir / "renders"
    renders_dir.mkdir(exist_ok=True)
    mp4_path = renders_dir / mp4_name
    logger.info(f"Rendering video to {mp4_path}...")
    run_cmd(["node", "tools/capture.mjs", "video", f"renders/{mp4_name}"], cwd=project_dir)

    # 8. Upload to S3
    logger.info("Uploading assets to S3...")
    s3_info = s3.upload_video_package(mp4_path, thumb_path, project_name=slug)

    # 9. Format English Publishing Package
    title = f"{topic} 🚗✨ #Shorts"
    description = f"Discover the surprising facts behind {topic}! Narrated with hyperrealistic AI voice and English subtitles. Subscribe for more amazing daily facts! #shorts"
    hashtags = ["#Shorts", "#DailyFacts", "#DidYouKnow", "#CarFacts", "#ViralShorts", "#MindBlowing"]

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
