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
RECENT = []

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
    return os.environ.get('UGC', 'off') == 'on' and random.random() < p

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

VOICE = os.environ.get('VOICE', 'Charon')  # one fixed narrator = recognisable brand voice
TTS_URL = 'https://natenathan.duckdns.org/webhook/cg-tts'
HIST_URL = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/video/history.json'

def gemini_tts(text, out_wav):
    """Narrator via n8n -> Gemini TTS (free tier). Handles WAV or raw 24k PCM. Returns True on success."""
    try:
        req = urllib.request.Request(TTS_URL, data=json.dumps({'text': text, 'voice': VOICE}).encode(), headers={'Content-Type': 'application/json'})
        r = json.load(urllib.request.urlopen(req, timeout=180))
        b = base64.b64decode(r.get('audio_b64') or '')
        if len(b) < 20000: return False
        if b[:4] == b'RIFF':
            open('tts_raw.wav', 'wb').write(b); src = ['-i', 'tts_raw.wav']
        else:
            open('tts_raw.pcm', 'wb').write(b); src = ['-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'tts_raw.pcm']
        sh(['ffmpeg', '-y'] + src + ['-af', 'silenceremove=start_periods=1:start_threshold=-45dB,loudnorm=I=-16:TP=-1.5', '-ar', '24000', '-ac', '1', out_wav])
        return True
    except Exception as e:
        print('gemini tts failed:', e); return False

def narrate(text, out_wav):
    if gemini_tts(text, out_wav):
        print('narrator: gemini', VOICE); return True
    if edge_tts(text, out_wav):
        print('narrator: edge backup'); return True
    return False

def history():
    try:
        h = get(HIST_URL)
        return h if isinstance(h, list) else []
    except Exception:
        return []

def fresh_choice(options, weights, recent, key):
    """Weighted pick that avoids whatever was used in the last 2 posts (keeps the feed varied, less 'automated')."""
    import random as _r
    used = [x.get(key) for x in recent[-2:]]
    opts = [(o, w) for o, w in zip(options, weights) if o not in used] or list(zip(options, weights))
    return _r.choices([o for o, _ in opts], [w for _, w in opts])[0]

def mix_voice_music(voice_wav, T, out_wav, starts=None):
    """Music bed ducked under the narrator (sidechain), plus scene whooshes."""
    pick_music(T, 'bed_raw.wav')
    bed = 'bed_raw.wav'
    if starts:
        try:
            add_whooshes('bed_raw.wav', starts, T, 'bed_w.wav'); bed = 'bed_w.wav'
        except Exception as e:
            print('whoosh skipped:', e)
    sh(['ffmpeg', '-y', '-i', voice_wav, '-i', bed, '-filter_complex',
        '[0:a]aresample=44100,apad=whole_dur=%.2f,asplit=2[v][sc];[1:a]volume=0.32[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];[v][md]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11[a]' % T,
        '-map', '[a]', '-t', '%.2f' % T, '-ar', '44100', '-ac', '2', out_wav])

def align_words(aud, segs, T):
    """Real word timings from the voiceover (free faster-whisper tiny.en on CPU).
    Returns (durs, wts) where wts[i] = absolute start time of every script word in segment i, or None."""
    try:
        import difflib
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'faster-whisper'], check=True, capture_output=True)
        from faster_whisper import WhisperModel
        m = WhisperModel('tiny.en', device='cpu', compute_type='int8')
        import numpy as np
        pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', aud, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], check=True, capture_output=True).stdout
        res, _ = m.transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0, word_timestamps=True, language='en', vad_filter=False)
        norm = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())
        rec = [(norm(w.word), float(w.start), float(w.end)) for sg in res for w in (sg.words or []) if norm(w.word)]
        script = [(i, norm(w)) for i, s in enumerate(segs) for w in str(s).split()]
        if not rec or not script:
            return None
        times = [None] * len(script)
        sm = difflib.SequenceMatcher(None, [x[1] for x in script], [r[0] for r in rec], autojunk=False)
        hit = 0
        for a, b, n in sm.get_matching_blocks():
            for k in range(n):
                times[a + k] = rec[b + k][1]; hit += 1
        if hit < 0.6 * len(script):
            print('word align: only %d/%d words matched, skipping' % (hit, len(script))); return None
        known = [k for k, t in enumerate(times) if t is not None]
        for k in range(len(times)):
            if times[k] is None:
                lo = max([j for j in known if j < k], default=None); hi = min([j for j in known if j > k], default=None)
                if lo is not None and hi is not None:
                    times[k] = times[lo] + (times[hi] - times[lo]) * (k - lo) / (hi - lo)
                elif lo is not None:
                    times[k] = min(times[lo] + 0.3 * (k - lo), T - 0.2)
                else:
                    times[k] = max(times[hi] - 0.3 * (hi - k), 0.0)
        for k in range(1, len(times)):
            times[k] = max(times[k], times[k - 1] + 0.05)
        wts = [[] for _ in segs]
        for (i, _), t in zip(script, times):
            wts[i].append(round(float(t), 3))
        starts = [0.0] + [max(wts[i][0] - 0.12, 0.0) if wts[i] else None for i in range(1, len(segs))]
        for i in range(1, len(starts)):
            if starts[i] is None or starts[i] <= starts[i - 1] + 0.4:
                starts[i] = starts[i - 1] + 0.4
        bounds = starts + [T]
        durs = [float(bounds[i + 1] - bounds[i]) for i in range(len(segs))]
        if any(x <= 0.3 for x in durs):
            return None
        print('word align: %d/%d words matched to the voice' % (hit, len(script)))
        return durs, wts
    except Exception as e:
        print('word align skipped:', e); return None

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

def pick_music(T, out_wav):
    import glob as _g, random as _rr
    bank = sorted(_g.glob('assets/music/*.mp3') + _g.glob('assets/music/*.m4a') + _g.glob('assets/music/*.wav'))
    if bank:
        recent = [x.get('music') for x in (globals().get('RECENT') or [])[-2:]]
        trk = _rr.choice([b for b in bank if os.path.basename(b) not in recent] or bank); print('music track:', trk)
        globals()['MUSIC_USED'] = os.path.basename(trk)
        sh(['ffmpeg', '-y', '-stream_loop', '-1', '-i', trk, '-t', '%.2f' % T, '-af', 'afade=t=in:d=0.2,afade=t=out:st=%.2f:d=1.0,volume=0.8' % max(T - 1.0, 0), '-ar', '44100', out_wav])
    else:
        music_bed(T, out_wav)

def add_whooshes(music_wav, starts, T, out_wav):
    """Subtle transition whoosh (filtered noise sweep) at each scene change, mixed under the music."""
    sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=0.45:c=pink:a=0.6', '-af',
        'highpass=f=700,lowpass=f=6000,afade=t=in:d=0.18,afade=t=out:st=0.2:d=0.25,volume=0.55', '-ar', '44100', '-ac', '2', 'whoosh.wav'])
    pts = [x for x in starts[1:] if 0.3 < x < T - 0.5]
    if not pts:
        os.replace(music_wav, out_wav); return
    ins = ['-i', music_wav]
    for _ in pts: ins += ['-i', 'whoosh.wav']
    fc = ''.join('[%d]adelay=%d|%d[w%d];' % (i + 1, int(max(0, x - 0.2) * 1000), int(max(0, x - 0.2) * 1000), i) for i, x in enumerate(pts))
    fc += '[0]' + ''.join('[w%d]' % i for i in range(len(pts))) + 'amix=inputs=%d:normalize=0:duration=first[a]' % (len(pts) + 1)
    sh(['ffmpeg', '-y'] + ins + ['-filter_complex', fc, '-map', '[a]', out_wav])

async def snap(template, data, T, transparent):
    shutil.rmtree('frames', ignore_errors=True); os.makedirs('frames')
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1080, 'height': 1920})
        await pg.goto('file://' + os.path.abspath(template))
        await pg.evaluate('setData(%s)' % json.dumps(data))
        await pg.wait_for_timeout(400)
        # readability gate: words touching / overflowing / too small -> fall back to the safe layout
        qa = await pg.evaluate('window.__qa || []')
        if qa and isinstance(data, dict) and 'd' in data:
            print('readability QA failed, switching to safe layout:', qa)
            d2 = data['d']
            if d2.get('hookStyle') == 'kinetic': d2['hookStyle'] = 'classic'
            if d2.get('pointStyle') == 'kinetic': d2['pointStyle'] = 'cards'
            d2['kinetic'] = False
            await pg.goto('file://' + os.path.abspath(template))
            await pg.evaluate('setData(%s)' % json.dumps(data))
            await pg.wait_for_timeout(400)
        else:
            print('readability QA passed')
        for i in range(int(FPS * T)):
            await pg.evaluate('setT(%f)' % (i / FPS))
            if transparent:
                await pg.screenshot(path='frames/f%04d.png' % i, type='png', omit_background=True)
            else:
                await pg.screenshot(path='frames/f%04d.jpg' % i, type='jpeg', quality=88)
        await b.close()

CHAIN_URL = 'https://natenathan.duckdns.org/webhook/gemini-chain'
CAPTION_RULES = (
    "You write the Instagram/Facebook caption for a short video by thecopygrind3r (Nathan, builds systems so estate agents and small "
    "local businesses answer every enquiry in minutes). TRW rules (Arno, Dylan, Andrew): the caption is NOT the video script. "
    "The viewer already saw the script on screen, so the caption adds what the video did not say: one short personal angle, a "
    "concrete detail, or an opinion someone could disagree with. Write like a real person typing on his phone: first person "
    "singular (I), plain words, short lines, 2 to 5 lines total, max 60 words before the call to action. Line 1 must make a "
    "scroller open the caption and must NOT repeat the on-screen hook. You may ask one genuine question to start comments. "
    "End with one natural ask that contains the exact word AUDIT in capitals (vary the wording, e.g. 'Drop AUDIT and I'll look "
    "at yours'). Never invent client results, numbers, names or testimonials; do not use any number that is not in the input. Never write we/our/us. Do not invent personal backstories (no 'I used to', no made-up events); opinions and what you see in your work are fine. Never "
    "mention school, training, age or private life. Never claim money or deals lost (no 'lose thousands') and no guarantees. No em dashes, no hashtags, max 1 emoji, no 'unlock, leverage, seamless, "
    "game-changer, elevate, in today's world, here's the thing'. Return JSON {\"caption\": \"...\"}."
)

def human_caption(d, fallback):
    """TRW caption writer: adds context instead of pasting the script. Falls back to the old caption if anything fails."""
    try:
        script = {'hook': d.get('hook') or d.get('title'), 'points': d.get('points') or [x.get('caption') for x in d.get('scenes', [])],
                  'recent_captions_to_avoid_repeating': [x.get('caption_l1') for x in RECENT[-5:] if x.get('caption_l1')]}
        payload = {'systemInstruction': {'parts': [{'text': CAPTION_RULES}]},
                   'contents': [{'parts': [{'text': json.dumps(script)}]}],
                   'generationConfig': {'responseMimeType': 'application/json', 'temperature': 1.0}}
        req = urllib.request.Request(CHAIN_URL, data=json.dumps({'payload': payload}).encode(), headers={'Content-Type': 'application/json'})
        r = json.load(urllib.request.urlopen(req, timeout=120))
        tx = ''.join(p.get('text', '') for p in r['candidates'][0]['content']['parts'] if not p.get('thought'))
        cap = json.loads(tx[tx.find('{'):tx.rfind('}') + 1])['caption'].strip()
        cap = re.sub(r'\s*[\u2014\u2013]\s*', ', ', cap)
        low = cap.lower(); norm = lambda x: re.sub(r'[^a-z0-9 ]', '', str(x).lower()).strip()
        lines = [norm(x) for x in [d.get('hook')] + (d.get('points') or []) if x and len(norm(x)) > 25]
        src_nums = set(re.findall(r'\d+', json.dumps(script)))
        bad_num = [n for n in re.findall(r'\d+', cap) if n not in src_nums]
        if 'AUDIT' not in cap or any(l in norm(cap) for l in lines) or len(cap) < 60 or bad_num or re.search(r"\b(we|we've|our|us)\b", low):
            print('caption rejected (missing AUDIT or copies the script):', cap[:120]); return fallback
        tags = re.findall(r'#\w+', fallback)
        tags = (['#thecopygrind3r'] + [t for t in tags if t.lower() != '#thecopygrind3r'])[:4]
        print('human caption:', cap.split('\n')[0])
        return cap + '\n\n' + ' '.join(tags)
    except Exception as e:
        print('caption writer failed, using script caption:', e); return fallback

def pick_audio_mode():
    """Variety: alternate narrator and music-only reels (env AUDIO_MODE overrides)."""
    m = os.environ.get('AUDIO_MODE', '').strip()
    if m in ('voice', 'music'): return m
    if os.environ.get('NARRATION') == 'off': return 'music'
    last = RECENT[-1] if RECENT else {}
    return 'music' if last.get('audio_mode') == 'voice' or (not last.get('audio_mode') and last.get('narrated')) else 'voice'

def guess_series(text):
    t = str(text or '').lower()
    if re.search(r'myth|wrong|mistake|stop |don.t|never', t): return 'MYTH vs FACT'
    if re.search(r'how to|step|checklist|guide|template|fix', t): return 'QUICK FIX'
    if re.search(r'night|11 ?pm|midnight|weekend|after hours|reply|enquir|lead', t): return 'LEAD LEAK'
    return 'AGENT PLAYBOOK'

def make_post_cover(d, bg=None):
    """Branded grid thumbnail for the reel (out/cover.jpg), same frame as carousel covers."""
    try:
        from cover import make_cover, short_title
        meta = {}
        mp = 'assets/gen/%s_meta.json' % d.get('id', '')
        if os.path.exists(mp): meta = json.load(open(mp))
        title = d.get('cover_title') or meta.get('cover_title') or short_title(d.get('title') or d.get('hook') or '')
        series = d.get('series') or meta.get('series') or guess_series((d.get('hook') or d.get('title') or '') + ' ' + ' '.join(d.get('points') or []))
        if not bg:
            hb = 'assets/gen/%s_hook_bg.jpg' % d.get('id', '')
            bg = hb if os.path.exists(hb) else None
        make_cover(title, series, 1080, 1920, 'out/cover.jpg', bg=bg)
        print('cover:', title, '|', series)
    except Exception as e:
        print('cover failed:', e)

def render_ad(d):
    os.makedirs('clips', exist_ok=True); os.makedirs('out', exist_ok=True)
    END = 2.4
    for sc in d['scenes']:  # Gemini sometimes leaks 'Line 1:' / 'Inbox Line 1:' labels into the phone UI
        sc['ui_lines'] = [re.sub(r'^\s*(?:\w+\s+)?line\s*\d+\s*:\s*', '', str(x), flags=re.I).strip() for x in (sc.get('ui_lines') or []) if str(x).strip()]
        sc['ui_title'] = re.sub(r'\s*(?:\w+\s+)?line\s*\d+\s*:.*$', '', str(sc.get('ui_title') or ''), flags=re.I).strip()
    parts = []
    voice = None
    AM = pick_audio_mode(); print('audio mode:', AM)
    if AM == 'voice':
        caps = [str(x.get('caption') or '').strip() for x in d['scenes']]
        spoken = ' '.join(c if c[-1:] in '.!?' else c + '.' for c in caps if c)
        if spoken and narrate(spoken, 'ad_voice.wav'):
            vd = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', 'ad_voice.wav']).decode().strip())
            tot = sum(x['dur'] for x in d['scenes'])
            if vd + 0.6 > tot:  # stretch scenes so the narrator never gets cut off
                k = (vd + 0.6) / tot
                for x in d['scenes']: x['dur'] = round(x['dur'] * k, 2)
            voice = 'ad_voice.wav'
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
        sh(['ffmpeg', '-y', '-stream_loop', '-1', '-ss', '%.2f' % ss, '-i', raw, '-t', '%.2f' % s['dur'], '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
        parts.append(out)
    sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x0b0b0d:s=1080x1920:r=%d:d=%.2f' % (FPS, END), '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', 'clips/end.mp4'])
    parts.append('clips/end.mp4')
    open('clips/list.txt', 'w').write(''.join("file '%s'\n" % os.path.basename(p) for p in parts))
    sh(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'clips/list.txt', '-c', 'copy', 'base.mp4'])
    T = sum(s['dur'] for s in d['scenes']) + END
    asyncio.run(snap('ad.html', d, T, True))
    st = [sum(x['dur'] for x in d['scenes'][:i]) for i in range(len(d['scenes']))]
    if voice:
        try:
            mix_voice_music(voice, T, 'music.wav', st)
        except Exception as e:
            print('voice mix failed, music only:', e); voice = None
    if not voice:
        pick_music(T, 'music.wav')
        sh(['ffmpeg', '-y', '-i', 'music.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', 'music_n.wav']); os.replace('music_n.wav', 'music.wav')
    sh(['ffmpeg', '-y', '-i', 'base.mp4', '-framerate', str(FPS), '-i', 'frames/f%04d.png', '-i', 'music.wav',
        '-filter_complex', '[0:v][1:v]overlay=0:0:shortest=1[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', 'out/latest.mp4'])
    try:
        sh(['ffmpeg', '-y', '-ss', '0.8', '-i', 'clips/s0.mp4', '-frames:v', '1', 'ad_bg.jpg'])
        make_post_cover({'id': d['id'], 'title': (d['scenes'][0].get('caption') if d.get('scenes') else d.get('title')), 'cover_title': d.get('cover_title'), 'series': 'LEAD LEAK'}, bg='ad_bg.jpg')
    except Exception as e:
        print('ad cover failed:', e)
    cap = clean_caption(human_caption(d, clean_caption(d['caption'])))
    json.dump({'date': d['date'], 'id': d['id'], 'caption': cap, 'caption_l1': cap.split('\n')[0][:120], 'audio_mode': AM if voice or AM == 'music' else 'music', 'duration': T, 'narrated': bool(voice), 'mode': 'ad', 'mechanism': d.get('mechanism'), 'music': globals().get('MUSIC_USED'), 'cover': os.path.exists('out/cover.jpg')}, open('out/meta.json', 'w'))
    print('rendered ad', d.get('mechanism'), T)

LABEL = re.compile(r'^\s*(?:\[?\s*(?:audio|vo|voice\s*over|voiceover|narrator|visual|on[- ]?screen(?: text)?|text overlay|overlay|caption|hook|cta|scene\s*\d*|slide\s*\d*|diagram|b-?roll|title)\s*\]?\s*[:\-\u2013]\s*)+', re.I)
# Captions are prose, so only 'Label:' or 'Label - ' counts (keeps words like 'Visual-first').
CAP_LABEL = re.compile(r'^\s*\[?\s*(?:audio|vo|voice\s*-?\s*over|narrator|visual|on[- ]?screen(?: text)?|text overlay|overlay|caption|hook|cta|scene\s*\d*|slide\s*\d*|beat\s*\d+|spoken|diagram|b-?roll|title)\s*\]?\s*(?::|\s[-\u2013]\s)\s*', re.I)
def clean_caption(c):
    """Strip script labels from every caption line before it is published (2 Nov: 'Audio:' leaked into Reel/Short/TikTok captions)."""
    out = []
    for l in str(c or '').split('\n'):
        prev = None
        while prev != l:
            prev, l = l, CAP_LABEL.sub('', l)
        out.append(l)
    return '\n'.join(out).strip()

def clean_line(x):
    """Strip script labels that leaked into on-screen text (seen live: 'Audio: New enquiry...')."""
    x = LABEL.sub('', str(x or '')).strip()
    x = re.sub(r'\[([^\]]{1,60})\]', r'\1', x).replace('->', '\u2192').strip()
    return x[:1].upper() + x[1:] if x else x

def render_daily(d):
    os.makedirs('out', exist_ok=True)
    d['hook'] = clean_line(d.get('hook')); d['points'] = [clean_line(x) for x in d.get('points', []) if clean_line(x)]; d['cta'] = clean_line(d.get('cta'))
    aud = None; adur = 0
    segs = [d['hook']] + d['points'] + ([d['statsLine']] if d.get('statsLine') else []) + [d['cta']]
    AM = pick_audio_mode(); print('audio mode:', AM)
    voice_on = AM == 'voice'
    if not voice_on:
        print('narration off: text + music')
    else:
        spoken = ' '.join(x.strip() if x.strip()[-1:] in '.!?' else x.strip() + '.' for x in segs if x.strip())
        if narrate(spoken, 'narr.wav'):
            aud = 'narr.wav'
    if aud:
        adur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', aud]).decode().strip())
    words = [max(len(s.split()), 3) for s in segs]
    if aud:
        T = max(adur + 1.0, 18.0)
    elif d.get('long'):
        T = min(max(46.0, sum(words) * 0.34 + len(segs) * 0.7), 58.0)
    else:
        T = min(max(16.0, sum(words) * 0.34 + len(segs) * 0.7), 42.0)
    durs = [T * w / sum(words) for w in words]
    wts = None
    al = align_words(aud, segs, T) if aud else None
    if al:
        durs, wts = al
    if aud and not al:
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
    kin_env = os.environ.get('KINETIC', '')
    if kin_env == 'on': d['hookStyle'], d['pointStyle'] = 'kinetic', 'kinetic'
    elif kin_env == 'off': d['hookStyle'], d['pointStyle'] = 'classic', 'cards'
    else:
        d['hookStyle'] = os.environ.get('HOOK_STYLE') or fresh_choice(['kinetic', 'notif', 'classic', 'countdown'], [0.35, 0.3, 0.15, 0.2], RECENT, 'hook_style')
        d['pointStyle'] = os.environ.get('POINT_STYLE') or fresh_choice(['kinetic', 'meter', 'cards', 'diagram'], [0.35, 0.3, 0.2, 0.15], RECENT, 'point_style')
    d['kinetic'] = d['hookStyle'] == 'kinetic'
    hb = 'assets/gen/%s_hook_bg.jpg' % d.get('id', '')
    if os.path.exists(hb):  # only faceless images made under the new rules (old ones had the AI character)
        shutil.copy(hb, 'hookbg.jpg'); d['hook_bg'] = 'hookbg.jpg'; print('using AI hook background')
    print('styles:', d['hookStyle'], d['pointStyle'])
    st0 = [sum(durs[:i]) for i in range(len(durs))]
    voiced = bool(aud)
    if aud:
        try:
            mix_voice_music(aud, T, 'mix.wav', st0); aud = 'mix.wav'
        except Exception as e:
            print('music under voice failed, voice only:', e)
    else:
        try:
            pick_music(T, 'music_raw.wav')
            try:
                add_whooshes('music_raw.wav', st0, T, 'music.wav')
            except Exception as e:
                print('whoosh skipped:', e); os.replace('music_raw.wav', 'music.wav')
            sh(['ffmpeg', '-y', '-i', 'music.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', 'music_n.wav']); os.replace('music_n.wav', 'music.wav')
            aud = 'music.wav'
        except Exception as e:
            print('music failed:', e)
    asyncio.run(snap('template.html', {'d': d, 'durs': durs, 'T': T, 'wts': wts}, T, False))
    cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i', 'frames/f%04d.jpg']
    if aud: cmd += ['-i', aud, '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', 'out/latest.mp4']
    sh(cmd)
    ai = False
    if d.get('hookStyle') == 'classic' and use_ugc(float(os.environ.get('UGC_DAILY_P', '0.4'))):
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
    make_post_cover(d)
    cap = clean_caption(human_caption(d, clean_caption(d['caption'])))
    json.dump({'date': d['date'], 'id': d['id'], 'caption': cap, 'caption_l1': cap.split('\n')[0][:120], 'audio_mode': AM if voiced or AM == 'music' else 'music', 'duration': T, 'narrated': voiced, 'ai_clip': ai, 'music': globals().get('MUSIC_USED'), 'mode': 'daily', 'cover': os.path.exists('out/cover.jpg'), 'hook_style': d.get('hookStyle'), 'point_style': d.get('pointStyle'), 'hook_bg': bool(d.get('hook_bg')), 'long': bool(d.get('long')), 'word_synced': bool(wts)}, open('out/meta.json', 'w'))
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
    RECENT = history()
    print('recent posts:', [(x.get('mode'), x.get('hook_style'), x.get('point_style'), x.get('music')) for x in RECENT[-3:]])
    if d.get('mode') == 'ad':
        render_ad(d)
    else:
        render_daily(d)
    try:
        m = json.load(open('out/meta.json'))
        json.dump((RECENT + [m])[-20:], open('out/history.json', 'w'))
    except Exception as e:
        print('history not saved:', e)
