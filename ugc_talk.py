"""AI UGC talking video of Nathan (his own reference photo, his consent), free.
Pipeline per segment: voice (Gemini TTS via n8n, or Chatterbox clone of Nathan's own voice
if VOICE_REF is set) -> Wan 2.2 image-to-video 'talking to phone camera' -> LatentSync lip-sync.
Then: join segments, burn word-chunk captions, light music bed, output 1080x1920 mp4.
Resumable: every finished step is saved under assets/talk/<job>/ and committed, so when the
free ZeroGPU quota runs out the next run continues where this one stopped."""
import os, json, time, shutil, subprocess, base64, urllib.request, random
from gradio_client import Client, handle_file

JOB = os.environ.get('JOB', '').strip()
if not JOB:
    base = os.path.join('assets', 'talk')
    open_jobs = sorted(j for j in (os.listdir(base) if os.path.isdir(base) else [])
                       if not os.path.exists(os.path.join(base, j, 'final.mp4')))
    if os.environ.get('RESUME_ONLY') and not open_jobs:
        print('nothing to resume'); raise SystemExit(0)
    JOB = open_jobs[-1] if open_jobs else time.strftime('%Y%m%d')
print('job', JOB, flush=True)
DIR = os.path.join('assets', 'talk', JOB)
os.makedirs(DIR, exist_ok=True)
PHOTO = os.environ.get('PHOTO') or 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
VOICE_REF = os.environ.get('VOICE_REF', '').strip()
TTS_URL = 'https://natenathan.duckdns.org/webhook/cg-tts'
tok = os.environ.get('HF_TOKEN') or None

DEFAULT = [
    "Most estate agents reply to a new enquiry the next day.",
    "By then, the renter has already booked three other viewings.",
    "So I built a system that replies in under two minutes, day or night.",
    "Comment AUDIT and I'll show you where your enquiries leak.",
]
spec_path = os.path.join(DIR, 'script.json')
if os.path.exists(spec_path):
    LINES = json.load(open(spec_path))
else:
    raw = os.environ.get('SCRIPT', '').strip()
    LINES = json.loads(raw) if raw else DEFAULT
    json.dump(LINES, open(spec_path, 'w'), indent=1)

MOTION = [
    'He talks to the phone camera like he is filming a casual TikTok, small natural head movements, one relaxed hand gesture, blinks normally.',
    'He keeps talking to the camera, leans in slightly, nods once, natural expression, subtle hand movement near the bottom of the frame.',
    'He explains something to the camera, raises his eyebrows a little, small shrug, natural blinking.',
]
STYLE = ' Handheld phone front camera, soft daylight, realistic skin, realistic subtle movement, no text on screen.'

def client(space):
    for _ in range(3):
        try:
            try: return Client(space, token=tok, verbose=False)
            except TypeError: return Client(space, hf_token=tok, verbose=False)
        except Exception as e:
            print('connect retry', space, str(e)[:120]); time.sleep(10)
    raise RuntimeError('cannot connect ' + space)

def quota(e):
    s = str(e).lower()
    return 'exceed' in s or 'quota' in s or 'gpu' in s and 'limit' in s

def dur(p):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())

def path_of(r):
    x = r[0] if isinstance(r, (list, tuple)) else r
    if isinstance(x, dict): x = x.get('video') or x.get('path') or x.get('value')
    if isinstance(x, dict): x = x.get('path')
    return x

_KOKORO = None
class SwitchVoice(Exception): pass
_vf = os.path.join(DIR, 'voice.txt')
ENGINE = [open(_vf).read().strip() if os.path.exists(_vf) else os.environ.get('VOICE_ENGINE', 'gemini')]
def kokoro_line(text, path):
    # open-source Kokoro (Apache-2.0, commercial use OK), runs on the CPU of the GitHub runner
    global _KOKORO
    import soundfile as sf
    if _KOKORO is None:
        from kokoro_onnx import Kokoro
        rel = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
        for f, u in (('kokoro.onnx', rel + 'kokoro-v1.0.int8.onnx'), ('voices.bin', rel + 'voices-v1.0.bin')):
            if not os.path.exists(f): urllib.request.urlretrieve(u, f)
        _KOKORO = Kokoro('kokoro.onnx', 'voices.bin')
    v = os.environ.get('KOKORO_VOICE', 'am_michael')
    a, sr = _KOKORO.create(text, voice=v, speed=1.05, lang='en-gb' if v.startswith('b') else 'en-us')
    sf.write(path, a, sr)

def voice_line(i, text):
    out = os.path.join(DIR, 'line%d.wav' % i)
    if os.path.exists(out): return out
    if VOICE_REF:
        r = client('ResembleAI/Chatterbox').predict(text_input=text, audio_prompt_path_input=handle_file(VOICE_REF),
              exaggeration_input=0.55, temperature_input=0.8, seed_num_input=0, cfgw_input=0.5, vad_trim_input=True,
              api_name='/generate_tts_audio')
        shutil.copy(path_of(r), out + '.tmp.wav')
    else:
        ok = False
        if ENGINE[0] == 'gemini':
            try:  # free tier is 10 requests/day: one try, then fall back
                req = urllib.request.Request(TTS_URL, data=json.dumps({'text': text, 'voice': os.environ.get('VOICE', 'Charon')}).encode(),
                                             headers={'Content-Type': 'application/json'})
                d = json.load(urllib.request.urlopen(req, timeout=150))
                if d.get('audio_b64'):
                    open(out + '.tmp.wav', 'wb').write(base64.b64decode(d['audio_b64'])); ok = True
            except Exception as e:
                print('gemini voice unavailable, using Kokoro:', str(e)[:80])
            if not ok:
                raise SwitchVoice()
        if not ok:
            kokoro_line(text, out + '.tmp.wav')
    # 48k mono, trimmed silence, short gap after each line
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out + '.tmp.wav', '-af',
                    'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.2,loudnorm=I=-16:TP=-1.5',
                    '-ar', '48000', '-ac', '1', out], check=True)
    os.remove(out + '.tmp.wav')
    return out

# camera-facing clips from the existing AI clip bank of Nathan (mouth visible, no props in front of the face)
BANK = ['bank_typing.mp4', 'ugc_20261025_0.mp4', 'ugc_20261028_3.mp4']

def pingpong(src, seconds, out):
    # forward, reversed, forward... until the clip covers the audio; drop the last 0.3 s of tail artefacts
    d = dur(src) - 0.3
    n = int(seconds // (2 * d)) + 1
    chain = '[0:v]trim=0:%.2f,setpts=PTS-STARTPTS,fps=25,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[p];' % d
    chain += '[p]' + ('split=%d' % n + ''.join('[p%d]' % k for k in range(n)) + ';' + ''.join('[p%d]' % k for k in range(n)) + 'concat=n=%d:v=1' % n if n > 1 else 'null') + '[v]'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', chain, '-map', '[v]', '-t', '%.2f' % (seconds + 0.2),
                    '-r', '25', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-an', out], check=True)

def motion(i, seconds):
    out = os.path.join(DIR, 'seg%d_raw.mp4' % i)
    if os.path.exists(out): return out
    if os.environ.get('MOTION', 'bank') == 'bank':
        # free GPU quota is ~3.5 min/day: reuse an existing clip so only lip-sync needs the GPU
        pingpong(os.path.join('assets', 'ugc', BANK[i % len(BANK)]), seconds, out)
        return out
    c = client('zerogpu-aoti/wan2-2-fp8da-aoti-faster')
    want = min(5.0, round(seconds + 0.3, 1))
    try:
        r = c.predict(input_image=handle_file(PHOTO), prompt=MOTION[i % len(MOTION)] + STYLE, duration_seconds=want,
                      steps=6, randomize_seed=True, api_name='/generate_video')
    except Exception as e:
        if quota(e): raise
        r = c.predict(input_image=handle_file(PHOTO), prompt=MOTION[i % len(MOTION)] + STYLE, duration_seconds=3.5,
                      randomize_seed=True, api_name='/generate_video')
    src = os.path.join(DIR, 'seg%d_wan.mp4' % i)
    shutil.copy(path_of(r), src)
    d = dur(src) - 0.3  # drop tail artefacts
    # cover the audio length: forward then reversed (ping-pong) if the clip is shorter
    if d < seconds:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex',
                        '[0:v]trim=0:%.2f,setpts=PTS-STARTPTS,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]' % d,
                        '-map', '[v]', '-t', '%.2f' % (seconds + 0.2), '-r', '25', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', out], check=True)
    else:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-t', '%.2f' % (seconds + 0.2), '-r', '25',
                        '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-an', out], check=True)
    return out

def lipsync(i, vid, wav):
    out = os.path.join(DIR, 'seg%d_sync.mp4' % i)
    if os.path.exists(out): return out
    r = client('fffiloni/LatentSync').predict(input_video_path=handle_file(vid), input_audio_path=handle_file(wav),
                                              api_name='/generate_lip_sync_video')
    shutil.copy(path_of(r), out)
    return out

def build_segments():
    # voice every line, then pack lines into segments of at most 7.4 s (LatentSync uses 8 s of audio)
    groups, cur, cur_d = [], [], 0.0
    for i, t in enumerate(LINES):
        d = dur(voice_line(i, t))
        if cur and cur_d + d > 7.4:
            groups.append(cur); cur, cur_d = [], 0.0
        cur.append(i); cur_d += d
    if cur: groups.append(cur)
    segs = []
    for g, idx in enumerate(groups):
        out = os.path.join(DIR, 'seg%d.wav' % g)
        if not os.path.exists(out):
            ins = sum([['-i', os.path.join(DIR, 'line%d.wav' % k)] for k in idx], [])
            subprocess.run(['ffmpeg', '-v', 'error', '-y'] + ins + ['-filter_complex',
                            ''.join('[%d:a]' % n for n in range(len(idx))) + 'concat=n=%d:v=0:a=1,adelay=120,apad=pad_dur=0.15[a]' % len(idx),
                            '-map', '[a]', '-t', '7.9', '-ar', '48000', '-ac', '1', out], check=True)
        segs.append(' '.join(LINES[k] for k in idx))
    return segs

done = True
try:
    try:
        SEGS = build_segments()
    except SwitchVoice:
        # one voice per video: redo every line with Kokoro
        ENGINE[0] = 'kokoro'
        for f in os.listdir(DIR):
            if f.startswith(('line', 'seg')): os.remove(os.path.join(DIR, f))
        SEGS = build_segments()
    open(_vf, 'w').write(ENGINE[0])
except Exception as e:
    print('voice step failed:', str(e)[:300]); SEGS = []; done = False
for i, text in enumerate(SEGS):
    try:
        wav = os.path.join(DIR, 'seg%d.wav' % i)
        vid = motion(i, dur(wav))
        lipsync(i, vid, wav)
        print('segment ok', i, flush=True)
    except Exception as e:
        print('stopped at segment', i, ':', str(e)[:300], flush=True)
        done = False
        break

if done:
    # captions: 3-4 word chunks timed across each segment's audio
    parts, t0, ass_lines = [], 0.0, []
    for i, text in enumerate(SEGS):
        p = os.path.join(DIR, 'seg%d_sync.mp4' % i); parts.append(p)
        d = dur(os.path.join(DIR, 'seg%d.wav' % i))
        words = text.split(); chunks = [' '.join(words[k:k + 3]) for k in range(0, len(words), 3)]
        span = (d - 0.4) / max(1, len(chunks))
        for k, ch in enumerate(chunks):
            a, b = t0 + 0.15 + k * span, t0 + 0.15 + (k + 1) * span
            f = lambda s: '%d:%02d:%05.2f' % (s // 3600, s % 3600 // 60, s % 60)
            ass_lines.append('Dialogue: 0,%s,%s,Cap,,0,0,0,,%s' % (f(a), f(b), ch.upper().replace(',', '')))
        t0 += dur(p)
    ass = os.path.join(DIR, 'caps.ass')
    open(ass, 'w').write('[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV\n'
        'Style: Cap,DejaVu Sans,74,&H00FFFFFF,&H00000000,&H64000000,1,1,6,0,2,560\n\n[Events]\n'
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n' + '\n'.join(ass_lines) + '\n')
    lst = os.path.join(DIR, 'list.txt')
    open(lst, 'w').write(''.join("file '%s'\n" % os.path.basename(p) for p in parts))
    joined = os.path.join(DIR, 'joined.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30',
                    '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', joined], check=True)
    music = [m for m in sorted(os.listdir('assets/music')) if m.endswith(('.mp3', '.wav', '.m4a'))] if os.path.isdir('assets/music') else []
    final = os.path.join(DIR, 'final.mp4')
    vf = 'subtitles=%s' % ass
    if music:
        m = os.path.join('assets/music', random.choice(music))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', joined, '-stream_loop', '-1', '-i', m, '-filter_complex',
                        '[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]',
                        '-map', '0:v', '-map', '[a]', '-vf', vf, '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', final], check=True)
    else:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', joined, '-vf', vf, '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', final], check=True)
    for f in os.listdir(DIR):  # keep the repo small: only script, final, and per-segment sync clips
        if f.endswith(('_wan.mp4', '_raw.mp4')) or f in ('joined.mp4', 'list.txt'):
            os.remove(os.path.join(DIR, f))
    print('FINAL', final, round(dur(final), 1), 's')
else:
    print('PARTIAL: will continue next run for job', JOB)
