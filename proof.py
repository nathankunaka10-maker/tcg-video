# Proof Reel (8 Nov 2026, Nathan approved): faceless, mysterious, and real.
# A narrated screen recording of a working prototype, run on an example business (never a real lead's name or data),
# recorded at phone size (1080x1920) so it looks native in the feed.
# TRW (AIC Instagram Growth): reels are the growth lever, the first seconds decide everything, one reel = one message,
# 'valuable advice' reels turn viewers into followers, and cheap visuals trigger cheap perception.
import json, os, re, subprocess, urllib.request, datetime

SHOWCASES = ['showcase-lettings', 'showcase-driving', 'showcase-dental', 'showcase-beauty']
DEMO = 'https://thecopygrind3r-demo.pages.dev/'
CFG = 'https://natenathan.duckdns.org/webhook/demo-config?a='
CHAIN = 'https://natenathan.duckdns.org/webhook/gemini-chain'
CTA = 'Comment AUDIT and I will show you where your enquiries get stuck.'
VW, VH, DSF = 432, 768, 2.5  # 1080x1920 output

def _get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'tcg-video'}), timeout=120))

def pick_showcase(recent):
    """Rotate through the example businesses, never the same one twice in a row."""
    if os.environ.get('SHOWCASE'): return os.environ['SHOWCASE']
    used = [x.get('showcase') for x in recent[-3:]]
    day = datetime.date.today().toordinal()
    order = SHOWCASES[day % len(SHOWCASES):] + SHOWCASES[:day % len(SHOWCASES)]
    return next((s for s in order if s not in used), order[0])

def write_script(cfg):
    ind = cfg.get('industry') or 'estate agency'
    sample = next((s for s in cfg.get('samples', []) if s.get('urgency') == 'high'), (cfg.get('samples') or [{}])[0]) if cfg.get('samples') else {}
    facts = {'business_type': ind, 'pain': (cfg.get('pain') or {}).get('en', ''), 'example_message_subject': sample.get('subject', ''),
             'what_the_system_does': [p.get('why_en') for p in cfg.get('plan', [])][:2]}
    prompt = ('You write the voiceover for a 15 to 20 second faceless Instagram Reel. On screen: a screen recording of a working demo '
              'that handles incoming enquiries for an EXAMPLE ' + ind + ' (not a real client). Viewer: owners of small local businesses and estate agents.\n'
              'Return JSON {hook, beats}. hook: max 9 words, a statement (never a question), speaks to the viewer (you/your), states the painful truth this demo fixes, never reveals the fix, like: Your enquiries go cold while you are on a viewing. '
              'beats: exactly 3 short spoken lines, max 13 words each, describing what the viewer sees in order: '
              '1) a real-looking enquiry lands (say it is a demo for a ' + ind + '), 2) the system reads it and picks out what matters, '
              '3) a full reply is drafted in seconds and a person just presses approve. '
              'Rules (TRW): one message only, never say we, our or us (say I or the system), plain words a Dutch reader understands, confident and calm. Never claim clients, results, '
              'percentages, money or time saved. No numbers. No em dashes, no emojis, no hashtags, no exclamation marks.\nFacts: ' + json.dumps(facts))
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.8, 'responseMimeType': 'application/json',
               'responseSchema': {'type': 'OBJECT', 'properties': {'hook': {'type': 'STRING'}, 'beats': {'type': 'ARRAY', 'items': {'type': 'STRING'}}}, 'required': ['hook', 'beats']}}}
    for m in ['gemini-2.5-flash', 'gemini-3.1-flash-lite']:
        try:
            req = urllib.request.Request(CHAIN, data=json.dumps({'model': m, 'payload': payload}).encode(), headers={'Content-Type': 'application/json'})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            t = ''.join(p.get('text', '') for p in r['candidates'][0]['content']['parts'] if not p.get('thought'))
            j = json.loads(t)
            clean = lambda s: re.sub(r'\s*[\u2014\u2013]\s*', ', ', str(s)).replace('!', '.').strip()
            hook, beats = clean(j['hook']), [clean(b) for b in j['beats']][:3]
            ok = (3 <= len(hook.split()) <= 11 and '?' not in hook and re.search(r'\b(you|your)\b', hook, re.I) and len(beats) == 3
                  and all(3 <= len(b.split()) <= 16 for b in beats) and not re.search(r'[0-9%€$]', hook + ' '.join(beats)) and not re.search(r'\b(we|our|us)\b', hook + ' ' + ' '.join(beats), re.I))
            if ok:
                return hook, beats
            print('proof script rejected:', hook, beats)
        except Exception as e:
            print('proof script failed on', m, e)
    return ('You are losing enquiries while you are busy',
            ['Here is a demo I built for a ' + ind + '. A new enquiry just landed.',
             'The system reads it and picks out what actually matters.',
             'A full reply is ready in seconds. You just press approve.'])

OVERLAY_CSS = """
#tcgo{position:fixed;inset:0;pointer-events:none;z-index:2147483647;font-family:Inter,'Helvetica Neue',Arial,sans-serif}
#tcgo .chip{position:absolute;top:14px;left:14px;background:rgba(10,14,22,.86);color:#7ee3f0;font:800 11px/1 Inter,Arial;letter-spacing:.12em;padding:8px 10px;border-radius:999px}
#tcgo .hook{position:absolute;left:16px;right:16px;top:118px;background:#0b1220;color:#fff;font:900 31px/1.12 Inter,Arial;padding:20px 20px;border-radius:18px;box-shadow:0 18px 50px rgba(0,0,0,.45);text-align:left}
#tcgo .hook b{color:#22d3ee}
#tcgo .cap{position:absolute;left:18px;right:18px;top:62px;text-align:center}
#tcgo .cap span{display:inline;background:#0b1220;color:#fff;font:800 23px/1.5 Inter,Arial;padding:5px 10px;border-radius:10px;box-decoration-break:clone;-webkit-box-decoration-break:clone}
#tcgo .cap span i{font-style:normal;color:#22d3ee}
#tcgo .ring{position:absolute;border:3px solid #22d3ee;border-radius:12px;box-shadow:0 0 0 9999px rgba(5,8,14,.28);transition:none}
#tcgo .end{position:absolute;inset:0;background:#0b1220;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;color:#fff;text-align:center;padding:0 34px}
#tcgo .end h2{font:900 34px/1.12 Inter,Arial;margin:0}
#tcgo .end .btn{background:#22d3ee;color:#0b1220;font:900 26px/1 Inter,Arial;padding:16px 26px;border-radius:14px}
#tcgo .end p{font:600 15px/1.4 Inter,Arial;color:#9fb3c8;margin:0}
"""

def record(slug, segs, durs, wts, T, fps, frames_dir, samples=None):
    """Deterministic frame-by-frame capture: scroll position, highlight ring and captions are set per frame."""
    from playwright.sync_api import sync_playwright
    os.makedirs(frames_dir, exist_ok=True)
    starts = [sum(durs[:i]) for i in range(len(durs))]
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=DSF)
        pg.goto(DEMO + slug, wait_until='networkidle', timeout=90000)
        pg.wait_for_timeout(1200)
        # English UI where the template offers it; hide the signature footer (Nathan stays anonymous for now).
        try:
            en = pg.get_by_text('English', exact=True)
            if en.count(): en.first.click(); pg.wait_for_timeout(500)
        except Exception: pass
        pg.evaluate("""() => { for (const el of document.querySelectorAll('body *')) { if (el.children.length < 4 && /Built by|Nathan|Kunaka|thecopygrind3r\\.pages/i.test(el.textContent || '')) el.style.visibility = 'hidden'; } }""")
        try:
            tab = pg.get_by_text('Inbox', exact=True)
            if tab.count(): tab.first.click(timeout=3000); pg.wait_for_timeout(600)
        except Exception: pass
        # open the most telling enquiry: an English one, else the urgent/high-value sample, else any sample
        subs = [x.get('subject') for x in sorted(samples or [], key=lambda x: 0 if x.get('urgency') == 'high' else 1) if x.get('subject')]
        opened = False
        for sel in ['text=Emily Carter'] + ['text="%s"' % sb.replace('"', '') for sb in subs] + ['text=/^Urgent$/', 'text=/High-value/']:
            loc = pg.locator(sel)
            for k in range(min(loc.count(), 3)):
                try: loc.nth(k).click(timeout=3000); opened = True; break
                except Exception: pass
            if opened: break
        if not opened:
            raise RuntimeError('could not open an enquiry on the demo page')
        pg.wait_for_timeout(1000)
        def ytop(sel):
            loc = pg.locator(sel)
            if not loc.count(): return None
            bb = loc.first.bounding_box()
            return None if not bb else bb['y'] + pg.evaluate('window.scrollY')
        def box(sel):
            loc = pg.locator(sel)
            if not loc.count(): return None
            bb = loc.first.bounding_box(); sy = pg.evaluate('window.scrollY')
            return None if not bb else {'x': bb['x'], 'y': bb['y'] + sy, 'w': bb['width'], 'h': bb['height']}
        maxy = pg.evaluate('document.documentElement.scrollHeight') - VH
        y_und = ytop('text=/WHAT THE SYSTEM (UNDERSTOOD|PICKED UP)/i')
        y_box = ytop('text=/MESSAGE AND ANALYSIS/i') or (y_und - 430 if y_und else None) or 900
        y_und = y_und or y_box + 430
        y_rep = ytop('text=/DRAFT REPLY/i') or y_und + 500
        approve = box('button:has-text("Approve")') or box('button:has-text("Goedkeuren")')
        clamp = lambda v: max(0, min(maxy, v))
        y_end = clamp((approve['y'] - VH * 0.5) if approve else y_rep + 300)  # Approve sits mid-screen, clear of the captions
        # camera path: hook = top of the demo, beat1 = the enquiry that just landed, beat2 = what the system understood,
        # beat3 = the drafted reply sliding down to the Approve button, cta = end card
        keys = [(0, 0), (starts[1], clamp(y_box - 60)), (starts[2], clamp(y_und - 60)), (starts[3], clamp(y_rep - 60)),
                (starts[3] + durs[3] * 0.45, y_end)]
        def cam(t):
            # each key = (moment the camera starts moving, target); it glides there in 1.1 s, then holds
            prev, cur = 0.0, 0.0
            for tk, yk in keys:
                if tk > t: break
                prev, cur, start = cur, yk, tk
            k = min(max((t - start) / 1.1, 0), 1)
            k = 1 - (1 - k) ** 3
            return prev + (cur - prev) * k
        pg.evaluate("""css => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
            const o = document.createElement('div'); o.id = 'tcgo'; o.innerHTML = '<div class=chip>DEMO \u00b7 EXAMPLE BUSINESS</div><div class=hook id=hk></div><div class=ring id=rg style=display:none></div><div class=cap><span id=cp></span></div><div class=end id=en style=display:none></div>'; document.body.appendChild(o);
            document.documentElement.style.scrollBehavior = 'auto'; }""", OVERLAY_CSS)
        hook = segs[0]
        hw = hook.split(); hk_html = ' '.join(('<b>%s</b>' % w) if i >= len(hw) - 2 else w for i, w in enumerate(hw))
        pg.evaluate("h => { document.getElementById('hk').innerHTML = h; }", hk_html)
        pg.evaluate("h => { document.getElementById('en').innerHTML = h; }",
                    '<h2>Want this running on your enquiries?</h2><div class=btn>Comment AUDIT</div><p>I will show you where your enquiries get stuck.<br>Demo with an example business. Nothing is sent without your OK.</p>')
        # caption chunks (3-4 words) timed to the voice when word timings exist
        chunks = []
        for i, s in enumerate(segs):
            ws = s.split(); tw = wts[i] if wts and i < len(wts) and len(wts[i]) == len(ws) else None
            for k in range(0, len(ws), 4):
                st = tw[k] if tw else starts[i] + durs[i] * k / max(len(ws), 1)
                chunks.append((st, i, ' '.join(ws[k:k + 4])))
        clicked = False
        n = int(fps * T)
        for f in range(n):
            t = f / fps
            seg = max(i for i in range(len(starts)) if starts[i] <= t + 1e-6)
            if seg == 3 and not clicked and approve and t >= starts[3] + durs[3] * 0.75:
                try: pg.locator('button:has-text("Approve")').first.click(timeout=1500)
                except Exception: pass
                clicked = True
            cur = [c for c in chunks if c[0] <= t and c[1] == seg]
            cap = cur[-1][2] if cur and seg not in (0, len(segs) - 1) else ''
            ring = None
            if seg == 3 and approve and t >= starts[3] + durs[3] * 0.55:
                ring = approve
            pg.evaluate("""a => { window.scrollTo(0, a.y);
                document.getElementById('hk').style.display = a.seg === 0 ? 'block' : 'none';
                const cp = document.getElementById('cp'); cp.textContent = a.cap; cp.style.display = a.cap ? 'inline' : 'none';
                document.getElementById('en').style.display = a.end ? 'flex' : 'none';
                const r = document.getElementById('rg');
                if (a.ring) { r.style.display = 'block'; r.style.left = (a.ring.x - 8) + 'px'; r.style.top = (a.ring.y - a.y - 8) + 'px'; r.style.width = (a.ring.w + 16) + 'px'; r.style.height = (a.ring.h + 16) + 'px'; } else r.style.display = 'none'; }""",
                        {'y': cam(t), 'seg': seg, 'cap': cap, 'end': seg == len(segs) - 1, 'ring': ring})
            pg.screenshot(path='%s/f%04d.jpg' % (frames_dir, f), type='jpeg', quality=88)
        b.close()
    return n

def render_proof(d, R):
    """R = the render module (narrate, align_words, mix_voice_music, human_caption, clean_caption, make_post_cover, sh, FPS, RECENT)."""
    os.makedirs('out', exist_ok=True)
    slug = pick_showcase(R.RECENT)
    cfg = _get(CFG + slug)
    if not cfg.get('slug'):
        raise RuntimeError('showcase config missing: ' + slug)
    hook, beats = write_script(cfg)
    segs = [hook] + beats + [CTA]
    print('proof reel:', slug, '|', hook, '|', beats)
    spoken = ' '.join(s if s[-1:] in '.!?' else s + '.' for s in segs)
    aud = 'narr.wav' if R.narrate(spoken, 'narr.wav') else None
    if aud:
        adur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', aud]).decode().strip())
        T = max(adur + 0.8, 12.0)
    else:
        T = 18.0
    words = [max(len(s.split()), 3) for s in segs]
    durs = [T * w / sum(words) for w in words]; wts = None
    al = R.align_words(aud, segs, T) if aud else None
    if al: durs, wts = al
    durs[0] = max(durs[0], 2.2)  # the hook must be readable
    T = sum(durs)
    st0 = [sum(durs[:i]) for i in range(len(durs))]
    if aud:
        try:
            R.mix_voice_music(aud, T, 'mix.wav', st0); aud = 'mix.wav'
        except Exception as e:
            print('music under voice failed, voice only:', e)
    else:
        R.pick_music(T, 'music.wav'); aud = 'music.wav'
    import shutil; shutil.rmtree('frames', ignore_errors=True)
    record(slug, segs, durs, wts, T, R.FPS, 'frames', cfg.get('samples'))
    cmd = ['ffmpeg', '-y', '-framerate', str(R.FPS), '-i', 'frames/f%04d.jpg']
    if aud: cmd += ['-i', aud, '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', 'out/latest.mp4']
    R.sh(cmd)
    dd = dict(d); dd.update({'hook': hook, 'points': beats, 'title': hook, 'series': 'BUILT IT', 'cover_title': hook})
    R.make_post_cover(dd)
    fallback = hook + '\n\n' + '\n'.join(beats) + '\n\nComment AUDIT and I will show you where your enquiries get stuck.\n\n#thecopygrind3r #automation #smallbusiness #aiautomation'
    cap = R.clean_caption(R.human_caption(dd, R.clean_caption(fallback)))
    json.dump({'date': d['date'], 'id': d['id'], 'caption': cap, 'caption_l1': cap.split('\n')[0][:120], 'audio_mode': 'voice' if aud == 'mix.wav' or aud == 'narr.wav' else 'music',
               'duration': T, 'narrated': aud in ('mix.wav', 'narr.wav'), 'ai_clip': False, 'music': getattr(R, 'MUSIC_USED', None), 'mode': 'proof', 'showcase': slug,
               'cover': os.path.exists('out/cover.jpg'), 'hook_style': 'proof', 'point_style': 'screen', 'word_synced': bool(wts)}, open('out/meta.json', 'w'))
    print('rendered proof reel', round(T, 1), 's')
