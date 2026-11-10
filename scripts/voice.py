"""Narration for $0 on this computer: Kokoro-82M text-to-speech (Apache-2.0) via kokoro-onnx. No account, no API.

  scripts/py scripts/voice.py <project>          script.json -> data/narration.wav + data/lines.json (exact line times)
  scripts/py scripts/voice.py --list             voices that narrate well
  scripts/py scripts/voice.py --download         only fetch the model files (~340 MB, once)

script.json: { "voice": "hf_beta", "lang": "hi", "speed": 1.05, "lead": 0.45, "outro": 0.9, "gap": 0.32,
               "lines": [ { "text": "क्या आपको पता है...", "caps": "...", "gap": 0.3 }, ... ] }
One line = one CUT, not one sentence: a sentence can run across several lines.
"""
import argparse, json, os, re, sys, urllib.request
from pathlib import Path
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from scipy.io import wavfile

HOME = Path(os.environ.get('FACELESS_HOME', Path.home() / '.faceless-shorts'))
KDIR = HOME / 'kokoro'
FILES = {
    'kokoro-v1.0.onnx': 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx',
    'voices-v1.0.bin': 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin',
}
GOOD = {
    'hi-IN-SwaraNeural': 'Hindi female, hyperrealistic Microsoft Azure Neural, warm & expressive (Free, No Key)',
    'en-US-AvaNeural': 'US female, hyperrealistic Microsoft Azure Neural, conversational & dynamic (Free, No Key)',
    'en-US-JennyNeural': 'US female, crisp, friendly Microsoft Azure Neural (Free, No Key)',
    'hf_beta': 'Hindi female, age 21, bright, expressive, conversational (Kokoro-82M local default)',
    'hf_alpha': 'Hindi female, age 21, warm, clear, calm (Kokoro-82M)',
    'hm_omega': 'Hindi male, expressive narrator (Kokoro-82M)',
    'hm_psi': 'Hindi male, deep explainer (Kokoro-82M)',
    'am_michael': 'US male, steady explainer', 'am_puck': 'US male, lively, playful', 'am_fenrir': 'US male, deeper',
    'am_onyx': 'US male, low', 'af_heart': 'US female, warm (best overall)', 'af_bella': 'US female, age 25, bright and conversational (default English)',
    'af_nicole': 'US female, soft and close', 'bm_george': 'UK male, documentary', 'bm_fable': 'UK male, storyteller',
    'bf_emma': 'UK female, calm',
}
SR = 24000


def synth_edge_tts(text, voice, speed=1.0):
    import asyncio, subprocess, edge_tts
    rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"-{int((1.0 - speed) * 100)}%"
    async def _run():
        comm = edge_tts.Communicate(text, voice, rate=rate_str)
        return b''.join([chunk['data'] async for chunk in comm.stream() if chunk['type'] == 'audio'])
    mp3_data = asyncio.run(_run())
    cmd = ['ffmpeg', '-y', '-f', 'mp3', '-i', 'pipe:0', '-f', 's16le', '-ar', str(SR), '-ac', '1', 'pipe:1']
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out, _ = p.communicate(input=mp3_data)
    return np.frombuffer(out, dtype=np.int16).astype(np.float64) / 32768.0


def synth_elevenlabs(text, voice_id, api_key):
    import subprocess, requests
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.20, "use_speaker_boost": True}
    }
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs error ({r.status_code}): {r.text}")
    cmd = ['ffmpeg', '-y', '-f', 'mp3', '-i', 'pipe:0', '-f', 's16le', '-ar', str(SR), '-ac', '1', 'pipe:1']
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out, _ = p.communicate(input=r.content)
    return np.frombuffer(out, dtype=np.int16).astype(np.float64) / 32768.0


def ensure_models():
    KDIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        p = KDIR / name
        if p.exists() and p.stat().st_size > 1_000_000: continue
        print(f'downloading {name} (once)...', flush=True)
        tmp = p.with_suffix('.part'); urllib.request.urlretrieve(url, tmp); tmp.rename(p)


def trim(x, thr=0.008):
    """cut leading/trailing silence so line start/end times are exact"""
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx): return x
    a = max(0, idx[0] - int(0.01 * SR)); b = min(len(x), idx[-1] + int(0.03 * SR)); return x[a:b]


def silences(x, thr=0.012, min_len=0.06):
    """pauses inside speech: [(start_s, end_s)] where the 10 ms RMS stays under thr for >= min_len"""
    hop = int(0.01 * SR); n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)); quiet = rms < thr * np.abs(x).max()
    out, st = [], None
    for f, q in enumerate(quiet):
        if q and st is None: st = f
        if (not q or f == n - 1) and st is not None:
            if (f - st) * 0.01 >= min_len: out.append((st * 0.01, f * 0.01))
            st = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project', nargs='?'); ap.add_argument('--list', action='store_true'); ap.add_argument('--download', action='store_true')
    ap.add_argument('--voice'); ap.add_argument('--speed', type=float); ap.add_argument('--lang')
    a = ap.parse_args()
    if a.list:
        for k, v in GOOD.items(): print(f'{k:12s} {v}')
        return
    if not a.project: ap.error('project folder missing')
    P = Path(a.project); S = json.loads((P / 'script.json').read_text(encoding='utf-8'))
    voice = a.voice or S.get('voice', 'hi-IN-SwaraNeural'); speed = a.speed or S.get('speed', 1.0)
    engine = S.get('engine', 'edge' if voice.endswith('Neural') else ('elevenlabs' if voice.startswith('elevenlabs:') else 'kokoro'))
    el_key = os.environ.get('ELEVENLABS_API_KEY')

    if engine == 'elevenlabs' or voice.startswith('elevenlabs:'):
        if not el_key:
            raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set. Please set it or use an edge-tts voice like 'hi-IN-SwaraNeural'.")
        voice_id = voice.split(':', 1)[1] if ':' in voice else 'EXAVITQu4vr4xnSDxMaL'
        print(f"Using ElevenLabs hyperrealistic voice: {voice_id}", flush=True)
        say = lambda text: trim(synth_elevenlabs(text, voice_id, el_key))
        lang = a.lang or S.get('lang', 'hi')
    elif engine == 'edge' or voice.endswith('Neural'):
        print(f"Using Microsoft Azure Neural voice (Edge-TTS): {voice} ({speed}x)", flush=True)
        say = lambda text: trim(synth_edge_tts(text, voice, speed))
        lang = a.lang or S.get('lang', 'hi' if 'hi-' in voice else 'en-us')
    else:
        ensure_models()
        from kokoro_onnx import Kokoro
        k = Kokoro(str(KDIR / 'kokoro-v1.0.onnx'), str(KDIR / 'voices-v1.0.bin'))
        lang = a.lang or S.get('lang') or ('hi' if voice.startswith('h') else ('en-gb' if voice.startswith('b') else 'en-us'))
        say = lambda text: trim(np.asarray(k.create(text, voice=voice, speed=speed, lang=lang)[0], dtype=np.float64))
    # group the lines into whole sentences (a line ending in . ? ! । closes one; "break": true forces a close)
    groups, cur = [], []
    for i, ln in enumerate(S['lines']):
        cur.append(i)
        if re.search(r'[.?!।]["\')]*$', ln['text'].strip()) or ln.get('break') or i == len(S['lines']) - 1: groups.append(cur); cur = []
    out = [np.zeros(int(S.get('lead', 0.4) * SR))]; t = len(out[0]) / SR; lines = [None] * len(S['lines'])
    for g in groups:
        x = say(' '.join(S['lines'][i]['text'] for i in g))
        cuts = [0.0]
        if len(g) > 1:                                    # find each cut inside the sentence
            lens = np.array([len(say(S['lines'][i]['text'])) for i in g], dtype=float)
            pauses = silences(x)
            for c in np.cumsum(lens)[:-1] / lens.sum() * len(x) / SR:
                near = [p for p in pauses if abs((p[0] + p[1]) / 2 - c) < 0.4]
                if near: p = min(near, key=lambda p: abs((p[0] + p[1]) / 2 - c)); cuts.append((p[0], p[1]))
                else: cuts.append((c, c))
        n = len(x) / SR
        for j, i in enumerate(g):
            a = 0.0 if j == 0 else cuts[j][1]; b = n if j == len(g) - 1 else cuts[j + 1][0]
            lines[i] = {'i': i, 'text': S['lines'][i]['text'], 'start': round(t + a, 3), 'end': round(t + b, 3)}
            print(f'{i:2d} {lines[i]["start"]:6.2f}-{lines[i]["end"]:6.2f}  {S["lines"][i]["text"]}', flush=True)
        gap = np.zeros(int(float(S['lines'][g[-1]].get('gap', S.get('gap', 0.3))) * SR))
        out += [x, gap]; t += (len(x) + len(gap)) / SR
    outro = np.zeros(int(float(S.get('outro', 0.9)) * SR)); out.append(outro)
    y = np.concatenate(out); y = y / (np.abs(y).max() + 1e-9) * 0.9
    (P / 'data').mkdir(exist_ok=True)
    wavfile.write(P / 'data/narration.wav', SR, (y * 32767).astype(np.int16))
    dur = len(y) / SR
    (P / 'data/lines.json').write_text(json.dumps({'duration': round(dur, 3), 'voice': voice, 'speed': speed, 'lang': lang, 'lines': lines}, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'data/narration.wav ({dur:.2f} s, {voice} [{lang}] x{speed}) + data/lines.json. Next: words.py')


if __name__ == '__main__':
    main()
