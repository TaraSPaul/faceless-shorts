"""
app.py — Bedrock AgentCore Runtime entrypoint for Faceless Shorts Generator.

The Bedrock AgentCore SDK exposes a single POST /invocations route.
All requests are routed here and dispatched internally based on the
'action' field in the payload.

Payload format:
---------------
{
    "action": "generate_short",
    "topic": "Why Does Your Speedometer Show More Speed?",
    "style": "inside-out",
    "voice": "elevenlabs:EXAVITQu4vr4xnSDxMaL",
    "lang": "hi",
    "script": { ... }
}

Endpoints auto-registered by the Bedrock AgentCore SDK:
    POST /invocations  <- all requests come here
    GET  /ping         <- health check (returns HEALTHY / HEALTHY_BUSY)
"""
import logging
import os
import sys
from pathlib import Path

# Add src to PYTHONPATH
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)
config.log_config()

from bedrock_agentcore import BedrockAgentCoreApp
from generator.pipeline import generate_short

app = BedrockAgentCoreApp()
logger.info("BedrockAgentCoreApp initialised for Faceless Shorts. Ready on port 8080.")


def _handle_generate_short(payload: dict) -> dict:
    """Handle short video generation request."""
    logger.info(f"[generate_short] payload: topic={payload.get('topic')}, style={payload.get('style')}")
    try:
        result = generate_short(payload)
        logger.info(f"[generate_short] complete: {result.get('video_url')}")
        return result
    except Exception as e:
        logger.exception(f"[generate_short] error: {e}")
        return {"status": "error", "error": str(e)}


def _handle_invoke(payload: dict) -> dict:
    """Handle direct invocation prompt."""
    prompt = payload.get("prompt", payload.get("topic", "")).strip()
    if not prompt:
        return {"error": "Missing 'prompt' or 'topic' in payload."}

    logger.info(f"[invoke] prompt: {prompt}")
    payload["topic"] = prompt
    return _handle_generate_short(payload)


@app.entrypoint
def handle_request(payload: dict) -> dict:
    """
    Main dispatch entrypoint for Bedrock AgentCore Runtime.
    Dispatches on the 'action' field in payload.
    """
    action = payload.get("action", "invoke")
    logger.info(f"[dispatch] action={action}")

    if action in ("generate_short", "create_video"):
        return _handle_generate_short(payload)
    elif action == "invoke":
        return _handle_invoke(payload)
    elif action == "ping":
        return {"status": "HEALTHY"}
    else:
        logger.warning(f"Unknown action '{action}' — defaulting to invoke")
        return _handle_invoke(payload)


if __name__ == "__main__":
    # Start the AgentCore HTTP server (default port 8080)
    app.run()
