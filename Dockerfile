# ────────────────────────────────────────────────────────────────────────────
# Bedrock AgentCore Runtime — Production Dockerfile for Faceless Shorts
#
# Architecture: linux/arm64 (AWS Graviton — required by Bedrock AgentCore Runtime)
# Multi-stage build with Chromium headless, Node.js 20, FFmpeg, and Python 3.11
# ────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/deps -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /deps /usr/local

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

WORKDIR /app

# Install native fast Canvas renderer (@napi-rs/canvas ARM64 prebuilt)
RUN npm install --prefix /app --no-save @napi-rs/canvas

# Copy application code, styles, and scripts
COPY src/ ./src/
COPY styles/ ./styles/
COPY scripts/ ./scripts/
COPY requirements.txt ./requirements.txt

RUN mkdir -p /tmp/shorts && chown -R appuser:appgroup /app /tmp/shorts

USER appuser

EXPOSE 8080

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV CHROME=/usr/bin/chromium
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CHROME_PATH=/usr/bin/chromium
ENV SOFTWARE_GL=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8080/ping || exit 1

CMD ["python", "-u", "src/app.py"]
