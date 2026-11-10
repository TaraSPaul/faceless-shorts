"""
test_agentcore.py — Invoke the live Faceless Shorts Bedrock AgentCore Runtime.

Usage:
  python scripts/test_agentcore.py <runtime_arn> [topic]
"""
import json
import sys
import boto3
from botocore.config import Config

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_agentcore.py <runtime_arn> [topic]")
        sys.exit(1)

    runtime_arn = sys.argv[1]
    topic = sys.argv[2] if len(sys.argv) > 2 else "Why Does Your Speedometer Show More Speed?"

    client = boto3.client(
        "bedrock-agentcore",
        region_name="us-east-1",
        config=Config(read_timeout=300, connect_timeout=30)
    )

    payload = {
        "action": "generate_short",
        "topic": topic,
        "style": "inside-out",
        "voice": "elevenlabs:EXAVITQu4vr4xnSDxMaL",
        "lang": "hi"
    }

    print(f"Invoking Bedrock AgentCore Runtime: {runtime_arn}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=json.dumps(payload).encode("utf-8"),
    )

    body = resp["response"].read().decode("utf-8")
    print("\nResponse:")
    try:
        print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    except Exception:
        print(body)

if __name__ == "__main__":
    main()
