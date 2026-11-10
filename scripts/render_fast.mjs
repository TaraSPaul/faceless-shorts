/**
 * render_fast.mjs — Native Rust/Skia Canvas 2D + raw RGBA FFmpeg renderer (no Chromium needed).
 *
 * Usage:
 *   node /app/scripts/render_fast.mjs cues [project_dir]
 *   node /app/scripts/render_fast.mjs video renders/out.mp4 [project_dir]
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
function loadNapiCanvas() {
  for (const candidate of [
    '@napi-rs/canvas',
    '/app/node_modules/@napi-rs/canvas',
    path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '../node_modules/@napi-rs/canvas'),
    'C:/tmp/bench-canvas/node_modules/@napi-rs/canvas',
  ]) {
    try {
      return require(candidate);
    } catch {}
  }
  throw new Error('Could not resolve @napi-rs/canvas');
}

const { createCanvas, GlobalFonts, loadImage } = loadNapiCanvas();

const args = process.argv.slice(2);
const mode = args[0];
const FPS = +(process.env.FPS || 24);
const ROOT = path.resolve(
  mode === 'cues' ? (args[1] || process.cwd()) : (args[2] || process.cwd())
);

// Polyfill browser fetch for timing.js
globalThis.fetch = async (rel) => {
  const filePath = path.join(ROOT, String(rel).split('?')[0]);
  if (!fs.existsSync(filePath)) return { ok: false, status: 404 };
  const text = fs.readFileSync(filePath, 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(text), text: async () => text };
};

// Register Inter font
const fontPath = path.join(ROOT, 'fonts/Inter-Black.otf');
if (fs.existsSync(fontPath)) {
  GlobalFonts.registerFromPath(fontPath, 'Inter');
}

// Preload and pre-rasterize episodic images (data/bg_*.jpg|png and data/illus_*.svg)
const dataDir = path.join(ROOT, 'data');
const illusList = [];
const bgList = [];

if (fs.existsSync(dataDir)) {
  const files = fs.readdirSync(dataDir);

  const bgFiles = files
    .filter((f) => /^bg_\d+\.(jpg|jpeg|png|webp)$/i.test(f))
    .sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));

  for (const f of bgFiles) {
    try {
      const img = await loadImage(fs.readFileSync(path.join(dataDir, f)));
      const maxDim = 1280;
      const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
      const tw = Math.max(1, Math.round(img.width * scale));
      const th = Math.max(1, Math.round(img.height * scale));
      const off = createCanvas(tw, th);
      off.getContext('2d').drawImage(img, 0, 0, tw, th);
      bgList.push(off);
    } catch (err) {
      console.error(`Warning: failed to load ${f}: ${err.message}`);
      bgList.push(null);
    }
  }

  const svgFiles = files
    .filter((f) => /^illus_\d+\.svg$/i.test(f))
    .sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));

  for (const f of svgFiles) {
    try {
      const img = await loadImage(fs.readFileSync(path.join(dataDir, f)));
      const off = createCanvas(840, 640);
      off.getContext('2d').drawImage(img, 0, 0, 840, 640);
      illusList.push(off);
    } catch (err) {
      console.error(`Warning: failed to load ${f}: ${err.message}`);
      illusList.push(null);
    }
  }
}
globalThis.__FAC_BGS__ = bgList;
globalThis.__FAC_ILLUS__ = illusList;

const importSrc = (rel) => import(pathToFileURL(path.join(ROOT, rel)).href);

const lib = await importSrc('src/core/lib.js');
const timing = await importSrc('src/core/timing.js');
const captions = await importSrc('src/core/captions.js');
const { buildShots } = await importSrc('src/shots.js');

const { W, H, setCtx, clamp, eo, eio } = lib;
const { T, loadTiming } = timing;
const { buildCaptions, drawCaption } = captions;

const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');
setCtx(ctx);

const script = JSON.parse(fs.readFileSync(path.join(ROOT, 'script.json'), 'utf8'));
await loadTiming();
buildCaptions(script);
const { shots, cues } = buildShots();
shots.sort((a, b) => a.at - b.at);
cues.sort((a, b) => a.t - b.t);

function drawFrame(t) {
  t = clamp(t, 0, T.dur - 1e-4);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.letterSpacing = '0px';
  ctx.fillStyle = '#070B14';
  ctx.fillRect(0, 0, W, H);

  let i = shots.length - 1;
  while (i > 0 && shots[i].at > t) i--;
  const sh = shots[i];
  const end = i < shots.length - 1 ? shots[i + 1].at : T.dur;
  const d = end - sh.at;
  const lt = t - sh.at;

  const punch = 1 + 0.08 * (1 - eo(clamp(lt / 0.28)));
  const drift = 1 + (sh.zoom ?? 0.04) * eio(clamp(lt / d));
  const [cx, cy] = sh.cam || [540, 620];

  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(punch * drift, punch * drift);
  ctx.translate(-cx, -cy);
  sh.draw(lt, d, t);
  ctx.restore();

  ctx.globalAlpha = 1;
  ctx.letterSpacing = '0px';
  if (i > 0 && lt < 0.12) {
    ctx.fillStyle = '#FFFFFF';
    ctx.globalAlpha = 0.45 * (1 - lt / 0.12);
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 1;
  }

  const fade = Math.min(clamp(t / 0.22), clamp((T.dur - t) / 0.32));
  if (fade < 1) {
    ctx.fillStyle = '#000';
    ctx.globalAlpha = 1 - fade;
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 1;
  }
  drawCaption(t);
}

if (mode === 'cues') {
  fs.mkdirSync(path.join(ROOT, 'data'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'data/cues.json'), JSON.stringify({ duration: T.dur, cues }, null, 1));
  console.log(`data/cues.json: ${cues.length} cues, ${T.dur.toFixed(2)} s`);
} else if (mode === 'video') {
  const out = path.resolve(ROOT, args[1] || 'renders/video.mp4');
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const thumbDir = path.join(ROOT, 'review/frames');
  fs.mkdirSync(thumbDir, { recursive: true });
  const thumbFrameIdx = Math.min(Math.round(2.0 * FPS), Math.max(0, Math.round(T.dur * FPS) - 1));

  const mix = path.join(ROOT, 'data/mix.wav');
  const hasMix = fs.existsSync(mix);
  const totalFrames = Math.round(T.dur * FPS);

  const ff = spawn(
    'ffmpeg',
    [
      '-v', 'error',
      '-y',
      '-f', 'rawvideo',
      '-pixel_format', 'rgba',
      '-video_size', `${W}x${H}`,
      '-framerate', String(FPS),
      '-i', '-',
      ...(hasMix ? ['-i', mix] : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']),
      '-map', '0:v',
      '-map', '1:a',
      '-c:v', 'libx264',
      '-preset', 'superfast',
      '-crf', '24',
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac',
      '-b:a', '192k',
      '-shortest',
      '-movflags', '+faststart',
      out,
    ],
    { stdio: ['pipe', 'inherit', 'inherit'] }
  );

  const t0 = Date.now();
  for (let idx = 0; idx < totalFrames; idx++) {
    drawFrame(idx / FPS);
    if (idx === thumbFrameIdx) {
      fs.writeFileSync(path.join(thumbDir, 't2.00.jpg'), canvas.toBuffer('image/jpeg', 92));
    }
    const raw = canvas.data();
    if (!ff.stdin.write(raw)) {
      await new Promise((r) => ff.stdin.once('drain', r));
    }
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on('close', (code) => (code === 0 ? res() : rej(new Error(`ffmpeg exited ${code}`)))));
  console.log(`${out} (${totalFrames} frames @ ${FPS}fps, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
} else {
  console.log('Usage: node render_fast.mjs [cues|video out.mp4] [project_dir]');
}
