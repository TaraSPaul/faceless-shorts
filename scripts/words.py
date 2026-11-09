"""Word timings with local Whisper or exact line-time spreading -> data/words.json [{w, line, s, e}].

  scripts/py scripts/words.py <project>                       after voice.py (uses data/narration.wav + data/lines.json)
  scripts/py scripts/words.py <project> --audio my_vo.m4a      YOUR OWN recording: becomes data/narration.wav
"""
import argparse, json, re, subprocess, sys
from difflib import SequenceMatcher
from pathlib import Path
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

norm = lambda w: re.sub(r'[^\w]+', '', w.lower())


def align(script_words, heard, t0, t1):
    """script_words: [str]; heard: [(word, s, e)] → [(s, e)] per script word, inside [t0, t1]"""
    a = [norm(w) for w in script_words]; b = [norm(h[0]) for h in heard]
    times = [None] * len(a)
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size): times[blk.a + k] = (heard[blk.b + k][1], heard[blk.b + k][2])
    # fill gaps between matched neighbours, split by word length
    i = 0
    while i < len(a):
        if times[i] is not None: i += 1; continue
        j = i
        while j < len(a) and times[j] is None: j += 1
        lo = times[i - 1][1] if i > 0 else t0; hi = times[j][0] if j < len(a) else t1
        if hi <= lo: hi = lo + 0.05 * (j - i)
        L = [max(1, len(a[k])) for k in range(i, j)]; tot = sum(L); c = lo
        for k, l in zip(range(i, j), L): d = (hi - lo) * l / tot; times[k] = (c, c + d * 0.9); c += d
        i = j
    return times


def inline_fallback(P, S):
    L = json.loads((P / 'data/lines.json').read_text(encoding='utf-8'))['lines']; words = []
    for i, ln in enumerate(S['lines']):
        toks = [w for w in ln['text'].split() if norm(w)]
        wts = [len(norm(w)) + 2.5 + (2.5 if (w.endswith(',') or w.endswith('।')) else 4.5 if re.search(r'[.?!।]$', w) and k < len(toks) - 1 else 0) for k, w in enumerate(toks)]
        lo, hi = L[i]['start'], L[i]['end']; c = lo; tot = sum(wts) if sum(wts) > 0 else 1
        for w, wt in zip(toks, wts):
            d = (hi - lo) * wt / tot; speak = d - (hi - lo) * (wt - len(norm(w)) - 2.5) / tot
            words.append({'w': w, 'line': i, 's': round(c, 3), 'e': round(c + speak * 0.92, 3)}); c += d
    (P / 'data/words.json').write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding='utf-8')
    (P / 'data/words.txt').write_text('\n'.join(f"{w['s']:7.2f} {w['e']:7.2f}  L{w['line']:<2d} {w['w']}" for w in words), encoding='utf-8')
    print(f'data/words.json: {len(words)} words (spread inside the voice line times)')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--audio'); a = ap.parse_args()
    P = Path(a.project); S = json.loads((P / 'script.json').read_text(encoding='utf-8'))
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel('small.en', device='cpu', compute_type='int8')
    except Exception as e:
        if a.audio or not (P / 'data/lines.json').exists():
            raise SystemExit(f'Whisper is needed for your own recording and could not load: {e}')
        print(f'Whisper unavailable ({type(e).__name__}); spreading words inside the exact line times instead')
        return inline_fallback(P, S)
    if a.audio:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.audio, '-ac', '1', '-ar', '24000', str(P / 'data/narration.wav')], check=True)
    try:
        import numpy as np
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(P / 'data/narration.wav'), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
        segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), word_timestamps=True, vad_filter=False)
        heard = [(w.word.strip(), w.start + 0.04, w.end) for s in segs for w in s.words]
    except Exception as e:
        if a.audio or not (P / 'data/lines.json').exists():
            raise SystemExit(f'Whisper could not transcribe the recording: {e}')
        print(f'Whisper failed ({type(e).__name__}: {e}); spreading words inside the exact line times instead')
        return inline_fallback(P, S)
    toks = [(w, i) for i, ln in enumerate(S['lines']) for w in ln['text'].split() if norm(w)]
    dur_audio = float(subprocess.run(['ffmpeg', '-v', 'error', '-i', str(P / 'data/narration.wav'), '-f', 'null', '-'], capture_output=True, text=True).stderr or 0) # duration
    try:
        times = align([w for w, _ in toks], heard, 0.0, float(json.loads((P / 'data/lines.json').read_text(encoding='utf-8'))['duration']))
    except Exception:
        return inline_fallback(P, S)
    words = [{'w': w, 'line': i, 's': round(s, 3), 'e': round(e, 3)} for (w, i), (s, e) in zip(toks, times)]
    if a.audio or not (P / 'data/lines.json').exists():
        lines = []
        for i, ln in enumerate(S['lines']):
            ws = [w for w in words if w['line'] == i]; lines.append({'i': i, 'text': ln['text'], 'start': ws[0]['s'], 'end': ws[-1]['e']})
        (P / 'data/lines.json').write_text(json.dumps({'duration': round(dur_audio, 3), 'lines': lines}, indent=1, ensure_ascii=False), encoding='utf-8')
    else:
        L = json.loads((P / 'data/lines.json').read_text(encoding='utf-8'))['lines']
        for w in words: lo, hi = L[w['line']]['start'], L[w['line']]['end']; w['s'] = round(min(max(w['s'], lo), hi), 3); w['e'] = round(min(max(w['e'], w['s']), hi), 3)
    (P / 'data/words.json').write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding='utf-8')
    (P / 'data/words.txt').write_text('\n'.join(f"{w['s']:7.2f} {w['e']:7.2f}  L{w['line']:<2d} {w['w']}" for w in words), encoding='utf-8')
    print(f'data/words.json: {len(words)} words (Whisper heard {len(heard)})')


if __name__ == '__main__':
    main()
