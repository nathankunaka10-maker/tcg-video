"""Invented AI presenter talking to camera with a small clip mic, cut with real screen recordings of the demo.
EUR 0: Gemini TTS (n8n webhook, Kokoro fallback), Wan2.2-S2V via the public Wan-AI Space (no ZeroGPU quota used)
or LongCat-Video-Avatar on ZeroGPU, Playwright screen recordings, faster-whisper word timings, ffmpeg.

The presenter is an invented person (assets/presenter/presenter_<X>.png), never Nathan and never a real person.
They speak as the brand's presenter: no testimonials, no customer claims, no invented results.
Every upload of the output to Instagram/Facebook MUST switch on Meta's AI label (see meta.json next to final.mp4).

Resumable: every finished step lives in assets/presenter/jobs/<job>/ and is committed by the workflow, so when
a free quota runs out the next dispatch with the same job continues where this one stopped."""
import os, json, time, shutil, subprocess, base64, urllib.request, random, re, math

ROOT = os.path.join('assets', 'presenter')
JOB = os.environ.get('JOB', '').strip()
if not JOB:
    base = os.path.join(ROOT, 'jobs')
    open_jobs = sorted(j for j in (os.listdir(base) if os.path.isdir(base) else [])
                       if not os.path.exists(os.path.join(base, j, 'final.mp4')))
    JOB = open_jobs[-1] if open_jobs else time.strftime('%Y%m%d')
DIR = os.path.join(ROOT, 'jobs', JOB)
os.makedirs(DIR, exist_ok=True)
print('job', JOB, flush=True)

cfg_path = os.path.join(DIR, 'job.json')
if os.path.exists(cfg_path):
    CFG = json.load(open(cfg_path))
else:
    raw = os.environ.get('SCRIPT', '').strip()
    CFG = {
        'lines': json.loads(raw) if raw else [
            "Most clinics miss about one in four calls when the front desk is busy.",
            "Those callers do not leave a message. They book somewhere else.",
            "So I set up a system that answers, asks what they need and books the slot.",
            "Here it is handling a missed call at nine at night.",
            "Comment LEAK and I will show you what yours is costing.",
        ],
        'presenter': (os.environ.get('PRESENTER') or 'A').strip().upper(),
        'model': (os.environ.get('MODEL') or 'ltx').strip(),
        'voice': (os.environ.get('VOICE') or '').strip(),
        'demo': os.environ.get('DEMO_URL') or 'https://thecopygrind3r-demo.pages.dev/example-lettings',
    }
    json.dump(CFG, open(cfg_path, 'w'), indent=1)
LINES = CFG['lines']
PHOTO = os.path.join(ROOT, 'presenter_%s.png' % CFG['presenter'])
# voices picked to match each invented presenter (Gemini prebuilt voices)
VOICE_FOR = {'A': 'Aoede', 'B': 'Achird', 'C': 'Callirrhoe'}
KOKORO_FOR = {'A': 'af_heart', 'B': 'am_michael', 'C': 'af_bella'}
SHOW_RE = re.compile(r'\b(here it is|watch this|look at this)\b', re.I)
SHOWCASE_GAP = float(os.environ.get('SHOWCASE_GAP', '3.6'))
TTS_URL = 'https://natenathan.duckdns.org/webhook/cg-tts'
tok = os.environ.get('HF_TOKEN') or None
W, H, FPS = 1080, 1920, 30

def run(args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, check=True)

def dur(p):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())

def client(space):
    from gradio_client import Client
    for _ in range(3):
        try:
            try: return Client(space, token=tok, verbose=False)
            except TypeError: return Client(space, hf_token=tok, verbose=False)
        except Exception as e:
            print('connect retry', space, str(e)[:120]); time.sleep(10)
    raise RuntimeError('cannot connect ' + space)

def path_of(r):
    x = r[0] if isinstance(r, (list, tuple)) else r
    for _ in range(3):
        if isinstance(x, dict): x = x.get('video') or x.get('path') or x.get('value') or x.get('url')
    return x

# ---------------------------------------------------------------- 1. voice (one take for the whole script)
def voice():
    clean = os.path.join(DIR, 'voice_clean.wav')
    if os.path.exists(clean): return clean
    raw = os.path.join(DIR, 'voice_raw.wav')
    text = ' '.join(LINES)
    try:  # Gemini free tier is ~10 requests a day: one request for the whole script, natural flow between lines
        v = CFG['voice'] or VOICE_FOR.get(CFG['presenter'], 'Aoede')
        req = urllib.request.Request(TTS_URL, data=json.dumps({'text': text, 'voice': v}).encode(),
                                     headers={'Content-Type': 'application/json'})
        d = json.load(urllib.request.urlopen(req, timeout=180))
        open(raw, 'wb').write(base64.b64decode(d['audio_b64']))
        CFG['voice_engine'] = 'gemini:' + v
    except Exception as e:
        print('gemini voice unavailable, using Kokoro:', str(e)[:120])
        import soundfile as sf, numpy as np
        from kokoro_onnx import Kokoro
        rel = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
        for f, u in (('kokoro.onnx', rel + 'kokoro-v1.0.int8.onnx'), ('voices.bin', rel + 'voices-v1.0.bin')):
            if not os.path.exists(f): urllib.request.urlretrieve(u, f)
        k = Kokoro('kokoro.onnx', 'voices.bin'); kv = KOKORO_FOR.get(CFG['presenter'], 'af_heart')
        parts = []
        for ln in LINES:
            a, sr = k.create(ln, voice=kv, speed=1.07, lang='en-us')
            parts += [a, np.zeros(int(sr * random.uniform(0.18, 0.32)), dtype=a.dtype)]
        sf.write(raw, np.concatenate(parts), sr)
        CFG['voice_engine'] = 'kokoro:' + kv
    json.dump(CFG, open(cfg_path, 'w'), indent=1)
    # trim edges, tighten long pauses a little (creator pacing), mono 48k, even loudness
    run(['-i', raw, '-af', 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,'
         'silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-45dB,adelay=150,apad=pad_dur=0.9,loudnorm=I=-16:TP=-1.5',
         '-ar', '48000', '-ac', '1', clean])
    os.remove(raw)
    return clean

def mic_room(clean):
    """Make TTS sound like a small wireless mic held near the chin in a normal room."""
    out = os.path.join(DIR, 'voice_mic.wav')
    if os.path.exists(out): return out
    d = dur(clean)
    # handling bumps: two soft low thumps where a hand shifts on the mic
    bumps = '+'.join('0.5*exp(-((t-%.2f)*40)^2)*sin(2*PI*55*t)' % random.uniform(0.5, d - 0.5) for _ in range(2))
    run(['-i', clean,
         '-f', 'lavfi', '-t', '%.2f' % d, '-i', 'anoisesrc=color=pink:amplitude=1:seed=7',
         '-f', 'lavfi', '-t', '%.2f' % d, '-i', 'aevalsrc=%s:s=48000' % bumps,
         '-filter_complex',
         # voice: lav-mic tone (thin low end, small presence lift), light comp, tiny early reflections of a room
         '[0:a]highpass=f=95,lowpass=f=14500,equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=250:t=q:w=1:g=-2,'
         'acompressor=threshold=-20dB:ratio=3:attack=8:release=120,aecho=0.85:0.5:13|27|41:0.10|0.06|0.035[v];'
         # room tone: pink noise shaped like HVAC/fridge hum, very low
         '[1:a]lowpass=f=900,highpass=f=60,volume=0.0035[n];'
         '[2:a]lowpass=f=150,volume=0.25[b];'
         '[v][n][b]amix=inputs=3:duration=first:normalize=0,loudnorm=I=-14:TP=-1.2[a]',
         '-map', '[a]', '-ar', '48000', '-ac', '1', out])
    return out

def words(clean):
    out = os.path.join(DIR, 'words.json')
    if os.path.exists(out): return json.load(open(out))
    from faster_whisper import WhisperModel
    m = WhisperModel('small.en', device='cpu', compute_type='int8')
    import soundfile as sf
    w16 = os.path.join(DIR, 'w16.wav'); run(['-i', clean, '-ar', '16000', '-ac', '1', w16])
    audio, _ = sf.read(w16, dtype='float32'); os.remove(w16)
    segs, _ = m.transcribe(audio, word_timestamps=True, language='en', initial_prompt=' '.join(LINES))
    ws = [{'w': w.word.strip(), 's': round(float(w.start), 3), 'e': round(float(w.end), 3)} for s in segs for w in s.words]
    # showcase beat: after the line that points at the product, leave ~3 s of just the screen recording
    i = 0
    for ln in LINES:
        i += len(ln.split())
        if SHOW_RE.search(ln) and 0 < i < len(ws):
            at, gap = ws[i - 1]['e'] + 0.15, SHOWCASE_GAP
            tmp = clean + '.tmp.wav'
            run(['-i', clean, '-filter_complex', '[0:a]atrim=0:%.3f,apad=pad_dur=%.3f[a];[0:a]atrim=start=%.3f,asetpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=0:a=1' % (at, gap, at),
                 '-ar', '48000', '-ac', '1', tmp])
            os.replace(tmp, clean)
            for w in ws[i:]: w['s'] = round(w['s'] + gap, 3); w['e'] = round(w['e'] + gap, 3)
            break
    json.dump(ws, open(out, 'w'), indent=0)
    return ws

# ---------------------------------------------------------------- 2. shot plan (A = presenter, B = screen recording)
def plan(ws, total):
    out = os.path.join(DIR, 'plan.json')
    if os.path.exists(out): return json.load(open(out))
    # which word starts each script line
    starts, i = [], 0
    for ln in LINES:
        starts.append(i); i += len(ln.split())
    starts = [min(s, len(ws) - 1) for s in starts]
    line_t = [ws[s]['s'] for s in starts] + [total]
    gaps = [0.0] + [(ws[k]['e'] + ws[k + 1]['s']) / 2 for k in range(len(ws) - 1)] + [total]
    def snap(t, lo, hi):
        c = [g for g in gaps if lo <= g <= hi]
        return min(c, key=lambda g: abs(g - t)) if c else t
    show = [k for k, ln in enumerate(LINES) if SHOW_RE.search(ln)]
    # 1. one shot per line, cut on the first word of each line: hook and call to action on the face,
    #    product lines (plus the silent showcase beat) on the inbox demo, the rest alternates
    bounds = [0.0] + [snap(line_t[k] - 0.06, line_t[k] - 0.4, line_t[k]) for k in range(1, len(LINES))] + [total]
    m, kind = [], 'A'
    for k in range(len(LINES)):
        if k == 0 or k == len(LINES) - 1: kind = 'A'
        elif k in show: kind = 'B'
        else: kind = 'B' if m[-1][0] == 'A' else 'A'
        m.append([kind, bounds[k], bounds[k + 1], 'inbox' if k in show else None])
    # 2. nothing longer than ~4 s (face shots no longer than A_MAX, what one model call can cover):
    #    the hook becomes face then screen, the CTA becomes screen then face (always end on the face),
    #    middle face shots become face then screen; long screen shots get a punch-in cut.
    A_MAX = 3.0 if CFG['model'] == 'ltx' else 4.0
    END = min(total, ws[-1]['e'] + 0.6)
    m[-1][2] = END
    out_m = []
    for n, sh in enumerate(m):
        kind, s0, e0, src = sh
        lim = A_MAX if kind == 'A' else 4.0
        if e0 - s0 <= lim: out_m.append(sh); continue
        if kind == 'A' and n == len(m) - 1:
            cut = snap(e0 - lim + 0.05, e0 - lim, e0 - 1.2)
            if e0 - cut > lim: cut = e0 - lim
            out_m += [['B', s0, cut, None], ['A', cut, e0, None]]
        elif kind == 'A':
            cut = snap(s0 + lim - 0.1, s0 + 1.2, s0 + lim)
            out_m += [['A', s0, cut, None], ['B', cut, e0, None]]
        else:
            cut = snap((s0 + e0) / 2, s0 + 1.8, e0 - 1.8)
            out_m += [[kind, s0, cut, src], [kind, cut, e0, src]]
    # 3. tiny screen shots next to another screen shot are merged when the result stays under ~4.2 s
    m2 = []
    for sh in out_m:
        if m2 and sh[0] == 'B' and m2[-1][0] == 'B' and (min(sh[2] - sh[1], m2[-1][2] - m2[-1][1]) < 1.5) and sh[2] - m2[-1][1] <= 4.2:
            m2[-1][2] = sh[2]; m2[-1][3] = m2[-1][3] or sh[3]
        else: m2.append(list(sh))
    out_m = m2
    rot, r = ['flow', 'assistant'], 0
    for sh in out_m:
        if sh[0] == 'B' and not sh[3]: sh[3] = rot[r % 2]; r += 1
    m = [[sh[0], round(float(sh[1]), 3), round(float(sh[2]), 3)] + ([sh[3]] if sh[0] == 'B' else []) for sh in out_m]
    json.dump(m, open(out, 'w'))
    return m

# ---------------------------------------------------------------- 3. talking presenter clips
def talk_wan(img, wav):
    c = client('Wan-AI/Wan2.2-S2V')
    from gradio_client import handle_file
    r = c.predict(ref_img=handle_file(img), audio=handle_file(wav), resolution='720P', api_name='/predict')
    return path_of(r)

def talk_longcat(img, wav):
    from gradio_client import handle_file
    c = client('victor/LongCat-Video-Avatar-1.5')
    r = c.predict(image_path=handle_file(img), audio_path=handle_file(wav),
                  prompt='A person filming a casual selfie video, talking to the phone camera while holding a small clip microphone below the chin, natural head movement, blinks, small hand gestures.',
                  resolution='480p', seed=random.randint(1, 9999), vocal_mode='Clean speech (fast)', acceleration='DBCache faster', api_name='/generate')
    return path_of(r)

LTX_PROMPT = ('A {who} films a casual vertical selfie video on a phone in an apartment, talking straight to the camera while holding '
              'a small black clip microphone just below the chin. Natural speech, natural lip movement, blinks, small head nods and tilts, '
              'relaxed eyebrows, the free hand moves a little. Soft window daylight, realistic skin, phone camera footage.')
WHO = {'A': 'young woman with dark brown hair', 'B': 'young man with short light brown hair and stubble', 'C': 'young woman with curly black hair in a bun'}

LTX_MAX = 3.0  # the Space's API fixes clip length at 3 s (its duration picker is UI-only), ~50 s of GPU per call

def talk_ltx(img, wav, seconds):
    """LTX-2 distilled (Lightricks), audio-conditioned image-to-video on the free alexnasa/ltx-2-TURBO ZeroGPU Space.
    Through the API every clip is 3 s (duration lives in private UI state). One call asks ~53 s of xlarge GPU,
    so a free account (300 s/day) gets about 3 presenter shots a day; resumable runs pick up the rest."""
    from gradio_client import handle_file
    c = client('alexnasa/ltx-2-TURBO')
    r = c.predict(first_frame=handle_file(img), end_frame=None, prompt=LTX_PROMPT.format(who=WHO.get(CFG['presenter'], 'young person')),
                  input_video=None, generation_mode='Image-to-Video', enhance_prompt=False, seed=random.randint(1, 99999), randomize_seed=False,
                  height=896, width=512, camera_lora='No LoRA', audio_path=handle_file(wav), api_name='/generate_video')
    return path_of(r)

def aroll_batch(shots, clean):
    """All presenter shots in as few model calls as possible: their audio is joined (with a short run-up before each),
    one talking clip is generated for the join, then cut back into the shots. The cuts sit next to screen-recording
    cuts, so the reset between pieces is never seen."""
    a = [(n, sh[1], sh[2]) for n, sh in enumerate(shots) if sh[0] == 'A']
    outs = {n: os.path.join(DIR, 'a%d.mp4' % n) for n, _, _ in a}
    if all(os.path.exists(o) for o in outs.values()): return outs
    RUN = 0.25
    # group shots into calls of at most 10 s
    groups, cur, cur_d = [], [], 0.0
    for n, s, e in a:
        d = (e - s) + min(RUN, s, max(0.0, LTX_MAX - (e - s)))
        if cur and cur_d + d > LTX_MAX + 0.01: groups.append(cur); cur, cur_d = [], 0.0
        cur.append((n, s, e)); cur_d += d
    if cur: groups.append(cur)
    for g, grp in enumerate(groups):
        if all(os.path.exists(outs[n]) for n, _, _ in grp): continue
        wav = os.path.join(DIR, 'talk%d.wav' % g)
        ins, fl = [], ''
        for j, (n, s, e) in enumerate(grp):
            pre = min(RUN, s, max(0.0, LTX_MAX - (e - s)))
            ins += ['-ss', '%.3f' % (s - pre), '-t', '%.3f' % (e - s + pre), '-i', clean]
            fl += '[%d:a]apad=whole_dur=%.3f[p%d];' % (j, (e - s + pre), j)
        fl += ''.join('[p%d]' % j for j in range(len(grp))) + 'concat=n=%d:v=0:a=1[a]' % len(grp)
        run(ins + ['-filter_complex', fl, '-map', '[a]', '-ar', '48000', '-ac', '1', wav])
        secs = LTX_MAX
        src = os.path.join(DIR, 'talk%d.mp4' % g)
        if os.path.exists(src) and dur(src) < dur(wav) - 0.3: os.remove(src)  # stale clip from a shorter request
        if not os.path.exists(src):
            r = talk_ltx(PHOTO, wav, secs)
            if str(r).startswith('http'): urllib.request.urlretrieve(r, src)
            else: shutil.copy(r, src)
            if dur(src) < dur(wav) - 0.3:
                raise RuntimeError('talking clip %.1f s shorter than audio %.1f s' % (dur(src), dur(wav)))
        t = 0.0
        for n, s, e in grp:
            pre = min(RUN, s, max(0.0, LTX_MAX - (e - s)))
            # piece starts at t: [run-up pre][shot (e - s)]
            run(['-ss', '%.3f' % (t + pre), '-i', src, '-t', '%.3f' % (e - s), '-an', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', outs[n]])
            t += (e - s) + pre
        os.remove(wav)
    return outs

def aroll(k, s, e, clean):
    out = os.path.join(DIR, 'a%d.mp4' % k)
    if os.path.exists(out): return out
    pad0 = min(0.6, s)  # give the model a little run-up so the mouth is already moving at the cut
    wav = os.path.join(DIR, 'a%d.wav' % k)
    run(['-ss', '%.3f' % (s - pad0), '-t', '%.3f' % (e - s + pad0 + 0.3), '-i', clean, '-ar', '16000', '-ac', '1', wav])
    fn = talk_longcat if CFG['model'] == 'longcat' else talk_wan
    src = fn(PHOTO, wav)
    if str(src).startswith('http'):
        urllib.request.urlretrieve(src, out + '.src.mp4')
    else:
        shutil.copy(src, out + '.src.mp4')
    run(['-ss', '%.3f' % pad0, '-i', out + '.src.mp4', '-t', '%.3f' % (e - s), '-an', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', out])
    os.remove(out + '.src.mp4'); os.remove(wav)
    return out

# ---------------------------------------------------------------- 4. screen recordings of the live demo
ZOOM = 2.5  # demo laid out as a 432 px wide phone inside an iframe, scaled up and recorded at 1080x1920
PHONE = '''<html><body style="margin:0;overflow:hidden;background:#fff;font-family:-apple-system,Inter,sans-serif">
<div style="transform:scale(%(z)s);transform-origin:0 0;width:432px;height:768px">
<div style="height:46px;display:flex;align-items:center;justify-content:space-between;padding:0 30px 0 34px;font-weight:600;font-size:16px;color:#111">
<span>%(clock)s</span><span style="display:flex;gap:6px;align-items:center">
<svg width="18" height="11"><rect x="0" y="7" width="3" height="4" rx="1"/><rect x="5" y="5" width="3" height="6" rx="1"/><rect x="10" y="2.5" width="3" height="8.5" rx="1"/><rect x="15" y="0" width="3" height="11" rx="1"/></svg>
<svg width="16" height="11" viewBox="0 0 16 11"><path d="M8 2.2c2.3 0 4.4.9 6 2.4l1.2-1.3A10.4 10.4 0 0 0 8 .4C5.2.4 2.7 1.5.8 3.3L2 4.6a8.6 8.6 0 0 1 6-2.4zm0 3.5c1.4 0 2.6.5 3.6 1.4L12.8 6A6.9 6.9 0 0 0 8 4a6.9 6.9 0 0 0-4.8 2l1.2 1.1c1-.9 2.2-1.4 3.6-1.4zM8 9.2l1.8-1.9a2.6 2.6 0 0 0-3.6 0z"/></svg>
<svg width="27" height="13"><rect x=".5" y=".5" width="23" height="12" rx="3.5" fill="none" stroke="#111" opacity=".45"/><rect x="2.5" y="2.5" width="14" height="8" rx="2"/><rect x="25" y="4.5" width="1.5" height="4" rx=".7" opacity=".45"/></svg></span></div>
<iframe src="%(url)s" style="border:0;width:432px;height:722px"></iframe></div></body></html>'''

def _glide(p, y, ms):
    """finger-like eased scroll"""
    y0 = p.evaluate('scrollY'); n = max(1, round(ms / 16))
    for i in range(1, n + 1):
        k = i / n; e = 2 * k * k if k < .5 else 1 - (-2 * k + 2) ** 2 / 2
        p.evaluate('v => scrollTo(0, v)', y0 + (y - y0) * e); p.wait_for_timeout(16)

def _tab(p, t):
    p.locator('button', has_text=t).first.click(); p.wait_for_timeout(900)

def _shot_inbox(p):
    _tab(p, 'Inbox'); _glide(p, 520, 1600); p.wait_for_timeout(700)
    _glide(p, 1180, 2600); p.wait_for_timeout(900)
    btn = p.locator('button', has_text='Approve and send').first
    btn.hover(); p.wait_for_timeout(500); btn.click(); p.wait_for_timeout(1800)

def _shot_flow(p):
    _glide(p, 420, 1200)
    try: p.locator('button', has_text='Play it step by step').first.click(timeout=3000)
    except Exception: pass
    p.wait_for_timeout(2500); _glide(p, 820, 2200); p.wait_for_timeout(1200)

def _shot_assistant(p):
    _tab(p, 'Website assistant'); _glide(p, 420, 1000)
    try: p.locator('button', has_text='Does anything get sent').first.click(timeout=3000)
    except Exception: pass
    p.wait_for_timeout(3500); _glide(p, 700, 1500); p.wait_for_timeout(1200)

def broll():
    """Real screen recordings of the live demo, phone-sized, recorded on the runner with Playwright."""
    from playwright.sync_api import sync_playwright
    d = os.path.join(DIR, 'broll')
    shots = {'inbox': _shot_inbox, 'flow': _shot_flow, 'assistant': _shot_assistant}
    res = {n: os.path.join(d, n + '.mp4') for n in shots}
    if all(os.path.exists(v) for v in res.values()): return res
    os.makedirs(d, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, fn in shots.items():
            if os.path.exists(res[name]): continue
            ctx = b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=1,
                                record_video_dir=d, record_video_size={'width': W, 'height': H})
            page = ctx.new_page()
            page.set_content(PHONE % {'z': ZOOM, 'url': CFG['demo'], 'clock': CFG.get('clock', '21:49')})
            page.wait_for_timeout(1500)
            p = page.frames[1]; p.wait_for_load_state('networkidle'); p.wait_for_timeout(800)
            fn(p); v = page.video; ctx.close()
            webm = v.path()
            # drop the page-load seconds
            run(['-ss', '2.6', '-i', webm, '-r', str(FPS), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', res[name]])
            os.remove(webm)
        b.close()
    return res

# ---------------------------------------------------------------- 5. captions (word by word, current word highlighted)
def captions(ws):
    def f(s): return '%d:%02d:%05.2f' % (s // 3600, s % 3600 // 60, s % 60)
    clean = [re.sub(r'[^\w\'%-]', '', w['w']) for w in ws]
    ev, k = [], 0
    while k < len(ws):  # groups of up to 3 words, break at sentence ends
        g = [k]
        while len(g) < 3 and g[-1] + 1 < len(ws) and not re.search(r'[.!?,]$', ws[g[-1]]['w']):
            g.append(g[-1] + 1)
        for j in g:
            end = ws[j + 1]['s'] if j + 1 < len(ws) and j != g[-1] else ws[j]['e'] + 0.12
            if j + 1 < len(ws) and j == g[-1]: end = min(ws[j]['e'] + 0.25, ws[j + 1]['s'])
            txt = ' '.join(('{\\c&H00D7FF&}%s{\\c&HFFFFFF&}' % clean[i].upper()) if i == j else clean[i].upper() for i in g)
            pop = '{\\fscx106\\fscy106\\t(0,90,\\fscx100\\fscy100)}' if j == g[0] else ''
            ev.append('Dialogue: 0,%s,%s,Cap,,0,0,0,,%s%s' % (f(ws[j]['s']), f(max(end, ws[j]['s'] + 0.08)), pop, txt))
        k = g[-1] + 1
    ass = os.path.join(DIR, 'caps.ass')
    open(ass, 'w').write('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        'Style: Cap,Inter,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,640,1\n\n[Events]\n'
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n' + '\n'.join(ev) + '\n')
    return ass

# ---------------------------------------------------------------- 6. assemble
def handheld(src, s_len, seed):
    """Upscale to 1080x1920 and add phone-in-hand micro movement, light grain, a touch of sharpening."""
    a, b, c = [random.Random(seed + i).uniform(0, 6.28) for i in range(3)]
    z = 1.06
    vf = ('scale=%d:%d:force_original_aspect_ratio=increase:flags=lanczos,crop=%d:%d,' % (int(W * z), int(H * z), int(W * z), int(H * z)) +
          "crop=%d:%d:x='(iw-ow)/2+14*sin(t*1.3+%.2f)+7*sin(t*3.1+%.2f)':y='(ih-oh)/2+18*sin(t*1.1+%.2f)+6*sin(t*2.7+%.2f)'," % (W, H, a, b, c, a) +
          'unsharp=5:5:0.45,noise=alls=7:allf=t,eq=saturation=1.03:contrast=1.02,fps=%d' % FPS)
    return vf

def assemble(shots, clips, brolls, voice_mic, ass):
    parts = []
    boff = {v: {'inbox': 1.4, 'flow': 1.0, 'assistant': 1.2}.get(k, 1.0) for k, v in brolls.items()}  # skip the page header
    for n, sh in enumerate(shots):
        kind, s, e = sh[:3]
        p = os.path.join(DIR, 'shot%d.mp4' % n)
        if kind == 'A':
            run(['-i', clips[n], '-vf', handheld(clips[n], e - s, n), '-t', '%.3f' % (e - s), '-an', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', p])
        else:
            src = brolls[sh[3]]
            start = boff.get(src, 0.0); start = min(start, max(0.0, dur(src) - (e - s) - 0.1)); boff[src] = start + (e - s)
            # screen recording: full frame, slow push-in so it does not feel static
            z0 = 1.16 if n and shots[n - 1][0] == 'B' and shots[n - 1][3] == sh[3] else 1.0  # punch-in cut
            vf = ("scale=%d:%d,zoompan=z='%.3f+0.035*on/(%d)':x='iw/2-(iw/zoom/2)':y='ih*0.42-(ih/zoom/2)':d=1:s=%dx%d:fps=%d,setsar=1"
                  % (W, H, z0, max(1, int((e - s) * FPS)), W, H, FPS))
            run(['-ss', '%.3f' % start, '-i', src, '-vf', vf, '-t', '%.3f' % (e - s), '-an', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', p])
        parts.append(p)
    lst = os.path.join(DIR, 'list.txt')
    open(lst, 'w').write(''.join("file '%s'\n" % os.path.basename(p) for p in parts))
    joined = os.path.join(DIR, 'joined.mp4')
    run(['-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', joined])
    final = os.path.join(DIR, 'final.mp4')
    run(['-i', joined, '-i', voice_mic, '-vf', 'subtitles=%s:fontsdir=/usr/share/fonts' % ass, '-map', '0:v', '-map', '1:a',
         '-c:v', 'libx264', '-crf', '19', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-r', str(FPS),
         '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', final])
    for p in parts + [lst, joined]: os.remove(p)
    for f in os.listdir(DIR):
        if f.startswith('talk') and f.endswith('.mp4'): os.remove(os.path.join(DIR, f))
    json.dump({'ai_generated': True, 'ai_label_required': True,
               'note': 'Realistic AI presenter. Switch on the AI label (Meta: "Add AI info" / made with AI) on every Instagram and Facebook upload.',
               'presenter': CFG['presenter'], 'model': CFG['model'], 'voice': CFG.get('voice_engine'), 'lines': LINES},
              open(os.path.join(DIR, 'meta.json'), 'w'), indent=1)
    return final

def main():
    random.seed(JOB)
    clean = voice()
    ws = words(clean)
    mic = mic_room(clean)
    shots = plan(ws, dur(clean))
    print('plan', shots, flush=True)
    brolls = broll()
    clips, ok = {}, True
    if CFG['model'] == 'ltx':
        try: clips = aroll_batch(shots, clean)
        except Exception as ex:
            print('stopped at presenter batch:', str(ex)[:300], flush=True); ok = False
    for n, sh in enumerate(shots if CFG['model'] != 'ltx' else []):
        kind, s, e = sh[:3]
        if kind != 'A': continue
        try:
            clips[n] = aroll(n, s, e, clean); print('presenter shot ok', n, flush=True)
        except Exception as ex:
            print('stopped at presenter shot', n, ':', str(ex)[:300], flush=True); ok = False; break
    if not ok:
        print('PARTIAL: dispatch again with job', JOB); return
    final = assemble(shots, clips, brolls, mic, captions(ws))
    print('FINAL', final, round(dur(final), 1), 's')

if __name__ == '__main__':
    main()
