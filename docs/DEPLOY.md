# Bedrock AgentCore Runtime — Faceless Shorts Deployment Guide

**Account**: `970817257663`  
**Region**: `us-east-1`  
**ECR Repository**: `970817257663.dkr.ecr.us-east-1.amazonaws.com/faceless-shorts-agent`  
**IAM Role ARN**: `arn:aws:iam::970817257663:role/faceless-shorts-agent-role`

---

## Architecture in Production

```
API Gateway / EventBridge / Lambda
        │
        │ {"action": "generate_short", "topic": "Why Speedometers Show More Speed", "voice": "..."}
        ▼
Bedrock AgentCore Runtime (POST /invocations on port 8080)
        │
        ├── 1. Parse topic & script lines
        ├── 2. Synthesize audio (ElevenLabs / Edge-TTS / Kokoro)
        ├── 3. Align word timestamps (words.py)
        ├── 4. Animate vector graphics in safe zones (shots.js)
        ├── 5. Headless Chromium render -> 1080x1920 MP4
        ├── 6. Upload MP4 and thumbnail to Amazon S3
        │
        ▼
POST /invocations Response
{
  "status": "success",
  "video_url": "https://s3.amazonaws.com/... (pre-signed)",
  "thumbnail_url": "https://s3.amazonaws.com/... (pre-signed)",
  "metadata": {
    "title": "Why Your Car Speedometer Is Actually Lying to You! 🚗⚡ #Shorts",
    "description": "...",
    "hashtags": ["#CarFacts", "#Automobile", "..."]
  }
}
```

The runtime exposes two endpoints automatically:
- `POST /invocations` — all video generation requests arrive here
- `GET /ping` — health check polled by Bedrock AgentCore

---

## Step 1 — Build and Push Image to ECR

### Option A: Via GitHub Actions (Recommended)
Push to `main` branch on [https://github.com/TaraSPaul/faceless-shorts](https://github.com/TaraSPaul/faceless-shorts). The `.github/workflows/deploy.yml` workflow automatically builds the `linux/arm64` container and pushes to Amazon ECR.

### Option B: Local Docker Buildx
```powershell
# 1. Login to Amazon ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 970817257663.dkr.ecr.us-east-1.amazonaws.com

# 2. Build arm64 image and push directly to ECR
docker buildx build `
  --platform linux/arm64 `
  -t 970817257663.dkr.ecr.us-east-1.amazonaws.com/faceless-shorts-agent:latest `
  --push .
```

### Option C: AWS CodeBuild (Native Graviton ARM64)
Uses the provisioned CodeBuild project `faceless-shorts-arm64-builder` with `buildspec.yml`:
```powershell
git archive --format=zip --output=$env:TEMP\faceless-shorts-src.zip HEAD
aws s3 cp $env:TEMP\faceless-shorts-src.zip s3://bedrock-agentcore-runtime-970817257663-us-east-1-2fikaiw53p/codebuild/source.zip
aws codebuild start-build --project-name faceless-shorts-arm64-builder --region us-east-1
```

Verify the image in ECR:
```powershell
aws ecr describe-images `
  --repository-name faceless-shorts-agent `
  --region us-east-1
```

---

## Step 2 — IAM Execution Role & Live Runtime

The IAM execution role and Bedrock AgentCore Runtime are provisioned in `us-east-1`:
- **Role Name**: `faceless-shorts-agent-role`
- **Role ARN**: `arn:aws:iam::970817257663:role/faceless-shorts-agent-role`
- **Attached Policies**: `AmazonS3FullAccess`, `CloudWatchLogsFullAccess`, `AmazonEC2ContainerRegistryReadOnly`, `AWSXrayWriteOnlyAccess`, and inline `BedrockAgentCoreWorkloadPolicy`
- **Runtime Name**: `faceless_shorts_agent`
- **Runtime ID**: `faceless_shorts_agent-G1o0APB8y8`
- **Runtime ARN**: `arn:aws:bedrock-agentcore:us-east-1:970817257663:runtime/faceless_shorts_agent-G1o0APB8y8`

---

## Step 3 — Environment Variables in Bedrock AgentCore

Configure the container runtime with these environment variables:
- `AWS_REGION`: `us-east-1`
- `OUTPUT_S3_BUCKET`: `bedrock-agentcore-runtime-970817257663-us-east-1-2fikaiw53p`
- `ELEVENLABS_API_KEY`: `sk_d5f9784376b22b0a180fb8e488dab39cdfa71299864d05ae`
- `DEFAULT_VOICE`: `elevenlabs:EXAVITQu4vr4xnSDxMaL`
- `DEFAULT_STYLE`: `inside-out`
- `DEFAULT_LANG`: `hi`

---

## Step 4 — Invoking the Agent

Send a `POST` request to `/invocations`:

```json
{
  "action": "generate_short",
  "topic": "Why Does Your Speedometer Show More Speed?",
  "style": "inside-out",
  "voice": "elevenlabs:EXAVITQu4vr4xnSDxMaL",
  "lang": "hi"
}
```

Test via `boto3` from PowerShell:
```powershell
python scripts/test_agentcore.py "arn:aws:bedrock-agentcore:us-east-1:970817257663:runtime/faceless_shorts_agent-G1o0APB8y8" "Why Do New Car Tires Have Tiny Rubber Hairs?"
```
