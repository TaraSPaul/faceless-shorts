"""
core/config.py — Configuration and validation for Faceless Shorts on Bedrock AgentCore.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
for env_path in [
    Path(__file__).resolve().parent.parent.parent / '.env',
    Path.cwd() / '.env',
    Path.home() / '.gemini/config/skills/faceless-shorts/.env'
]:
    if env_path.exists():
        load_dotenv(env_path)
        break

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
OUTPUT_S3_BUCKET = os.environ.get("OUTPUT_S3_BUCKET", "bedrock-agentcore-runtime-970817257663-us-east-1-2fikaiw53p")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "elevenlabs:EXAVITQu4vr4xnSDxMaL")
DEFAULT_STYLE = os.environ.get("DEFAULT_STYLE", "inside-out")
DEFAULT_LANG = os.environ.get("DEFAULT_LANG", "hi")

def log_config():
    logger.info("=== Faceless Shorts AgentCore Configuration ===")
    logger.info(f"AWS_REGION        : {AWS_REGION}")
    logger.info(f"OUTPUT_S3_BUCKET  : {OUTPUT_S3_BUCKET}")
    logger.info(f"ELEVENLABS_API_KEY: {'[SET]' if ELEVENLABS_API_KEY else '[NOT SET]'}")
    logger.info(f"GOOGLE_API_KEY    : {'[SET]' if GOOGLE_API_KEY else '[NOT SET]'}")
    logger.info(f"GEMINI_IMAGE_MODEL: {GEMINI_IMAGE_MODEL}")
    logger.info(f"DEFAULT_VOICE     : {DEFAULT_VOICE}")
    logger.info(f"DEFAULT_STYLE     : {DEFAULT_STYLE}")
    logger.info(f"DEFAULT_LANG      : {DEFAULT_LANG}")
    logger.info("===============================================")
