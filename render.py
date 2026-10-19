import asyncio, subprocess, os, json, shutil, base64, urllib.request, datetime, re, sys
from playwright.async_api import async_playwright

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
def fetch(url, dst, tries=3):
    import time
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://pixabay.com/', 'Accept': '*/*'})
            with urllib.request.urlopen(req, timeout=120) as r, open(dst, 'wb') as f:
                shutil.copyfileobj(r, f)
            if os.path.getsize(dst) > 10000:
                return
            last = Exception('file too small')
        except Exception as e:
            last = e
        time.sleep(2 * (k + 1))
    raise last
FEED = 'https://natenathan.duckdns.org/webhook/video-content'
AD_FEED = 'https://natenathan.duckdns.org/webhook/ad-content'
FPS = 30
AD_DAYS = (1, 4)  # Tuesday, Friday (UTC weekday)
UGC_BASE = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/ugc/'
UGC_CLIPS = ['clip1.mp4', 'bank_typing.mp4', 'bank_phone.mp4']
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'tcg-video'})
    return json.load(urllib.request.urlopen(req, timeout=240))

def ugc_pick():
    """Random AI clip of Nathan: uses manifest.json (grows weekly), falls back to the seed clips."""
    import random
    names = UGC_CLIPS
    try:
        m = get(UGC_BASE + 'manifest.json')
        if isinstance(m, list) and m:
            names = m
    except Exception as e:
        print('manifest unavailable, using seed clips:', e)
    return random.choice(names)

def use_ugc(p):
    import random
    return os.environ.get('UGC', 'on') != 'off' and random.random() < p

def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)

def edge_tts(text, out_wav, voice='en-GB-RyanNeural'):
    """Free backup voice (Microsoft Edge TTS). Returns True on success."""
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'edge-tts'], check=True, capture_output=True)
        subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', voice, '--rate=+4%', '--text', text, '--write-media', 'vo.mp3'], check=True, capture_output=True, timeout=180)
        sh(['ffmpeg', '-y', '-i', 'vo.mp3', '-ar', '24000', '-ac', '1', out_wav])
        return True
    except Exception as e:
        print('edge-tts failed:', e); return False

def music_bed(seconds, out_wav):
    """Royalty-free bed synthesised from scratch: soft chord pad, kick, hats. Nothing licensed."""
    bpm = 96.0; beat = 60.0 / bpm; bar = beat * 4
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    terms = []
    for ci, ch in enumerate(chords):
        sel = 'between(mod(t,%.4f),%.4f,%.4f)' % (bar * 4, bar * ci, bar * (ci + 1) - 0.001)
        tone = '+'.join('0.06*sin(2*PI*%.2f*t)+0.025*sin(2*PI*%.2f*t)' % (f, f * 2) for f in ch)
        terms.append('%s*(%s)' % (sel, tone))
    pad = '(' + '+'.join(terms) + ')*(0.75+0.25*sin(2*PI*t/%.4f))' % beat
    kick = '0.55*sin(2*PI*(48+70*exp(-30*mod(t,%.4f)))*mod(t,%.4f))*exp(-9*mod(t,%.4f))' % (beat, beat, beat)
    hat = '0.05*(random(0)*2-1)*exp(-60*mod(t+%.4f,%.4f))' % (beat / 2, beat)
    expr = '%s+%s+%s' % (pad, kick, hat)
    sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'aevalsrc=%s:s=44100:d=%.2f' % (expr.replace(',', '\\,'), seconds),
        '-af', 'lowpass=f=5000,afade=t=in:d=0.4,afade=t=out:st=%.2f:d=1.2,volume=0.6' % max(seconds - 1.2, 0), out_wav])

async def snap(template, data, T, transparent):
    shutil.rmtree('frames', ignore_errors=True); os.makedirs('frames')
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1080, 'height': 1920})
        await pg.goto('file://' + os.path.abspath(template))
        await pg.evaluate('setData(%s)' % json.dumps(data))
        await pg.wait_for_timeout(400)
        for i in range(int(FPS * T)):
            await pg.evaluate('setT(%f)' % (i / FPS))
            if transparent:
                await pg.screenshot(path='frames/f%04d.png' % i, type='png', omit_background=True)
            else:
                await pg.screenshot(path='frames/f%04d.jpg' % i, type='jpeg', quality=88)
        await b.close()

def render_ad(d):
    os.makedirs('clips', exist_ok=True); os.makedirs('out', exist_ok=True)
    END = 2.4
    parts = []
    ugc_i = None
    if len(d['scenes']) >= 3 and use_ugc(float(os.environ.get('UGC_AD_P', '0.6'))):
        ugc_i = 1  # middle scene becomes an AI clip of Nathan (labelled)
    for i, s in enumerate(d['scenes']):
        raw = 'clips/raw%d.mp4' % i
        is_ai = False
        if i == ugc_i:
            try:
                import random
                fetch(UGC_BASE + ugc_pick(), raw)
                is_ai = True
            except Exception as e:
                print('ugc clip failed, using stock:', e)
        if not is_ai:
            try:
                fetch(s['clip'], raw)
            except Exception as e:
                print('stock clip failed:', e)
                try:
                    fetch(UGC_BASE + ugc_pick(), raw); is_ai = True
                except Exception as e2:
                    print('ugc fallback failed, using plain background:', e2)
                    sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x15161a:s=1080x1920:r=%d:d=%.2f' % (FPS, s['dur'] + 1), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', raw])
        try:
            src = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', raw]).decode().strip())
        except Exception:
            src = 0
        ss = max(min(1.0, src - s['dur'] - 0.1), 0) if src else 0
        # crop to 9:16, gentle punch-in over the scene so stock feels handheld/edited
        z = '1.0+0.06*t/%.2f' % s['dur']
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "scale=w='trunc(1080*(%s)/2)*2':h='trunc(1920*(%s)/2)*2':eval=frame,crop=1080:1920,"
              "setsar=1,fps=%d,eq=saturation=1.08:contrast=1.04" % (z, z, FPS))
        out = 'clips/s%d.mp4' % i
        sh(['ffmpeg', '-y', '-ss', '%.2f' % ss, '-i', raw, '-t', '%.2f' % s['dur'], '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
        parts.append(out)
    sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x0b0b0d:s=1080x1920:r=%d:d=%.2f' % (FPS, END), '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', 'clips/end.mp4'])
    parts.append('clips/end.mp4')
    open('clips/list.txt', 'w').write(''.join("file '%s'\n" % os.path.basename(p) for p in parts))
    sh(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'clips/list.txt', '-c', 'copy', 'base.mp4'])
    T = sum(s['dur'] for s in d['scenes']) + END
    asyncio.run(snap('ad.html', d, T, True))
    music_bed(T, 'music.wav')
    sh(['ffmpeg', '-y', '-i', 'base.mp4', '-framerate', str(FPS), '-i', 'frames/f%04d.png', '-i', 'music.wav',
        '-filter_complex', '[0:v][1:v]overlay=0:0:shortest=1[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', 'out/latest.mp4'])
    json.dump({'date': d['date'], 'id': d['id'], 'caption': d['caption'], 'duration': T, 'narrated': False, 'mode': 'ad', 'mechanism': d.get('mechanism')}, open('out/meta.json', 'w'))
    print('rendered ad', d.get('mechanism'), T)

def render_daily(d):
    os.makedirs('out', exist_ok=True)
    aud = None; adur = 0
    segs = [d['hook']] + d['points'] + [d['statsLine'], d['cta']]
    if d.get('audio_b64'):
        open('narr.pcm', 'wb').write(base64.b64decode(d['audio_b64']))
        sh(['ffmpeg', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'narr.pcm', 'narr.wav'])
        aud = 'narr.wav'
    elif edge_tts(' ... '.join(segs), 'narr.wav'):
        aud = 'narr.wav'
        print('used Edge TTS backup voice')
    if aud:
        adur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', aud]).decode().strip())
    words = [max(len(s.split()), 3) for s in segs]
    T = max(adur + 1.0, 18.0)
    durs = [T * w / sum(words) for w in words]
    if aud:
        try:
            log = subprocess.run(['ffmpeg', '-i', aud, '-af', 'silencedetect=noise=-35dB:d=0.25', '-f', 'null', '-'], capture_output=True, text=True).stderr
            ss = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', log)]
            se = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', log)]
            gaps = [(e - s, (s + e) / 2) for s, e in zip(ss, se) if 0.15 < s < adur - 0.3]
            need = len(segs) - 1
            if len(gaps) >= need:
                mids = sorted(m for _, m in sorted(gaps, reverse=True)[:need])
                bounds = [0.0] + mids + [T]
                nd = [bounds[i + 1] - bounds[i] for i in range(len(segs))]
                if all(x > 0.6 for x in nd):
                    durs = nd; print('synced to voiceover pauses')
        except Exception as e:
            print('pause sync skipped:', e)
    import random as _r
    kp = float(os.environ.get('KINETIC_P', '0.5'))
    d['kinetic'] = os.environ.get('KINETIC', '') == 'on' or (os.environ.get('KINETIC', '') != 'off' and _r.random() < kp)
    hb = 'assets/gen/%s_hook.jpg' % d.get('id', '')
    if os.path.exists(hb):
        shutil.copy(hb, 'hookbg.jpg'); d['hook_bg'] = 'hookbg.jpg'; print('using AI hook background')
    print('kinetic' if d['kinetic'] else 'classic', 'style')
    asyncio.run(snap('template.html', {'d': d, 'durs': durs, 'T': T}, T, False))
    cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i', 'frames/f%04d.jpg']
    if aud: cmd += ['-i', aud, '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', 'out/latest.mp4']
    sh(cmd)
    ai = False
    if not d.get('kinetic') and use_ugc(float(os.environ.get('UGC_DAILY_P', '0.4'))):
        try:
            hook = min(durs[0], 5.0)
            fetch(UGC_BASE + ugc_pick(), 'ugc.mp4')
            fc = ("[1:v]scale=1080:1170:force_original_aspect_ratio=increase,crop=1080:1170,setsar=1,fps=%d[c];"
                  "[0:v][c]overlay=0:10:enable='between(t,0,%.2f)'[v]" % (FPS, hook))
            sh(['ffmpeg', '-y', '-i', 'out/latest.mp4', '-stream_loop', '-1', '-t', '%.2f' % hook, '-i', 'ugc.mp4',
                '-filter_complex', fc, '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
                '-c:a', 'copy', '-t', '%.2f' % T, '-movflags', '+faststart', 'out/ugc_mix.mp4'])
            os.replace('out/ugc_mix.mp4', 'out/latest.mp4'); ai = True
            print('added AI cutaway on hook')
        except Exception as e:
            print('ugc cutaway skipped:', e)
    json.dump({'date': d['date'], 'id': d['id'], 'caption': d['caption'], 'duration': T, 'narrated': bool(aud), 'ai_clip': ai, 'kinetic': bool(d.get('kinetic')), 'hook_bg': bool(d.get('hook_bg'))}, open('out/meta.json', 'w'))
    print('rendered', T)

if __name__ == '__main__':
    local = sys.argv[1] if len(sys.argv) > 1 else ''
    if local:  # local test: python render.py payload.json
        d = json.load(open(local))
    else:
        d = None
        mode = os.environ.get('MODE', '').strip().lower()
        if mode == 'ad' or (mode != 'daily' and datetime.datetime.utcnow().weekday() in AD_DAYS):
            try:
                a = get(AD_FEED)
                if a.get('scenes') and not a.get('skip'):
                    d = a
            except Exception as e:
                print('ad feed failed, falling back to daily video:', e)
        if d is None:
            d = get(FEED)
    if d.get('skip'):
        print('nothing to render today'); raise SystemExit(0)
    if d.get('mode') == 'ad':
        render_ad(d)
    else:
        render_daily(d)
