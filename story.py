# Story Reel (8 Nov 2026, Nathan approved option 2): the faceless character + a true behind-the-build story, 1-2x a week.
# TRW (AIC Instagram Growth): storytelling creates retention, retention creates distribution; one reel = one message.
# Only TRUE facts about what Nathan has built go in (no invented events, clients, results or numbers). If the faceless
# clip bank is still empty, render.py falls back to a Proof Reel.
import json, os, re, random, subprocess, urllib.request

BANK = os.environ.get('FACELESS_BANK', 'assets/faceless')
CHAIN = 'https://natenathan.duckdns.org/webhook/gemini-chain'
CTA = 'Comment AUDIT and I will show you where your enquiries get stuck.'
# True statements about systems Nathan has built and runs (keep this list factual; add new builds as they go live).
FACTS = [
    'I built a system that gives every lead a personal working demo of a reply assistant, set up with their own business name and services, before I ever pitch them.',
    'I built a call list that knows when each business is open, so I only call while they can pick up, and it sorts who to call first.',
    'Before I email a business, my system reads their website and looks for one specific thing that is costing them customers.',
    'My system checks every reply twice a day, catches bounces and out-of-office messages, and only follows up when it adds something new.',
    'I built a dashboard that pulls every number in my business into one page, so I see in one look what is working and what is not.',
    'If a lead does not reply to my email, my system puts them on my call list two days later with a note of what I sent.',
    'Every enquiry demo I build drafts a reply in the business\'s own tone and nothing is ever sent without a person pressing approve.',
    'My own content runs on a pipeline that writes, records and posts a video every day without me touching it.',
]

def bank():
    try:
        m = json.load(open(os.path.join(BANK, 'manifest.json')))
    except Exception:
        return []
    return [os.path.join(BANK, x) for x in m if os.path.exists(os.path.join(BANK, x))]

def write_script(recent):
    used = [x.get('story_fact') for x in recent[-6:]]
    pool = [f for f in FACTS if f not in used] or FACTS
    fact = random.choice(pool)
    prompt = ('Write the voiceover for a 15 to 20 second faceless Instagram story Reel. The narrator is a young builder of automation '
              'systems talking in first person (I), calm and confident. The visuals show him only from behind or his hands.\n'
              'The story must be built ONLY on this true fact: ' + fact + '\n'
              'Return JSON {hook, beats}. hook: max 10 words, a statement (never a question) that creates tension or curiosity for small '
              'business owners and estate agents, e.g. the problem that made him build it. beats: exactly 3 spoken lines, max 14 words each: '
              '1) the problem most businesses have, 2) what he built (from the fact), 3) what changes for the owner. '
              'Rules (TRW): one message, plain words a Dutch reader understands. Never invent events, clients, results, money, percentages or '
              'numbers. Never mention school, age, training or private life. No em dashes, no emojis, no hashtags, no exclamation marks.')
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.85, 'responseMimeType': 'application/json',
               'responseSchema': {'type': 'OBJECT', 'properties': {'hook': {'type': 'STRING'}, 'beats': {'type': 'ARRAY', 'items': {'type': 'STRING'}}}, 'required': ['hook', 'beats']}}}
    for m in ['gemini-2.5-flash', 'gemini-3.1-flash-lite']:
        try:
            req = urllib.request.Request(CHAIN, data=json.dumps({'model': m, 'payload': payload}).encode(), headers={'Content-Type': 'application/json'})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            t = ''.join(p.get('text', '') for p in r['candidates'][0]['content']['parts'] if not p.get('thought'))
            j = json.loads(t)
            clean = lambda s: re.sub(r'\s*[—–]\s*', ', ', str(s)).replace('!', '.').strip()
            hook, beats = clean(j['hook']), [clean(b) for b in j['beats']][:3]
            txt = hook + ' ' + ' '.join(beats)
            if (3 <= len(hook.split()) <= 12 and '?' not in hook and len(beats) == 3 and all(3 <= len(b.split()) <= 17 for b in beats)
                    and not re.search(r'[0-9%€$]', txt) and not re.search(r'\b(school|class|teacher|exam|age|years old|we|our|us)\b', txt, re.I)):
                return fact, hook, beats
            print('story script rejected:', hook, beats)
        except Exception as e:
            print('story script failed on', m, e)
    return fact, 'Most businesses lose enquiries without ever noticing', ['Messages wait for hours while the owner is busy.', 'So I built ' + fact.split('I built ', 1)[-1].split(',')[0].rstrip('.') + '.', 'Now nothing slips through and every reply goes out fast.']

def ass_time(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return '%d:%02d:%05.2f' % (h, m, s)

def build_ass(segs, durs, wts, T, path):
    """Hook as a big bold title, then word-timed 3-4 word captions, then the AUDIT end card."""
    starts = [sum(durs[:i]) for i in range(len(durs))]
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Hook,Inter,96,&H00FFFFFF,&H00FFFFFF,&H00201208,&H64000000,1,0,0,0,100,100,0,0,3,26,0,8,70,70,330,1',
             'Style: Cap,Inter,74,&H00FFFFFF,&H00FFFFFF,&H00201208,&H00000000,1,0,0,0,100,100,0,0,3,18,0,2,80,80,520,1',
             'Style: End,Inter,92,&H00FFFFFF,&H00FFFFFF,&H00201208,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,80,80,0,1',
             'Style: Btn,Inter,84,&H00201208,&H00201208,&H00EED322,&H00000000,1,0,0,0,100,100,0,0,3,24,0,5,80,80,0,1', '',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    hw = segs[0].split()
    hook = ' '.join(('{\\c&HEED322&}%s{\\c&HFFFFFF&}' % w) if i >= len(hw) - 2 else w for i, w in enumerate(hw))
    lines.append('Dialogue: 1,%s,%s,Hook,,0,0,0,,%s' % (ass_time(0), ass_time(starts[1]), hook))
    for i in range(1, len(segs) - 1):
        ws = segs[i].split(); tw = wts[i] if wts and i < len(wts) and len(wts[i]) == len(ws) else None
        ch = list(range(0, len(ws), 4))
        for n, k in enumerate(ch):
            a = tw[k] if tw else starts[i] + durs[i] * k / len(ws)
            b = (tw[ch[n + 1]] if tw else starts[i] + durs[i] * ch[n + 1] / len(ws)) if n + 1 < len(ch) else starts[i] + durs[i]
            lines.append('Dialogue: 1,%s,%s,Cap,,0,0,0,,%s' % (ass_time(a), ass_time(b), ' '.join(ws[k:k + 4])))
    e0 = starts[-1]
    lines.append('Dialogue: 0,%s,%s,End,,0,0,0,,{\\pos(540,800)}Want this running\\Non your enquiries?' % (ass_time(e0), ass_time(T)))
    lines.append('Dialogue: 1,%s,%s,Btn,,0,0,0,,{\\pos(540,1010)}Comment AUDIT' % (ass_time(e0), ass_time(T)))
    open(path, 'w').write('\n'.join(lines) + '\n')

def render_story(d, R):
    clips = bank()
    if len(clips) < 3:
        raise RuntimeError('faceless clip bank has %d clips, need 3' % len(clips))
    os.makedirs('out', exist_ok=True)
    fact, hook, beats = write_script(R.RECENT)
    segs = [hook] + beats + [CTA]
    print('story reel:', hook, '|', beats)
    spoken = ' '.join(s if s[-1:] in '.!?' else s + '.' for s in segs)
    aud = 'narr.wav' if R.narrate(spoken, 'narr.wav') else None
    if not aud:
        raise RuntimeError('no narrator available for a story reel')
    adur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', aud]).decode().strip())
    T = max(adur + 0.8, 12.0)
    words = [max(len(s.split()), 3) for s in segs]
    durs = [T * w / sum(words) for w in words]; wts = None
    al = R.align_words(aud, segs, T)
    if al: durs, wts = al
    durs[0] = max(durs[0], 2.2); T = sum(durs)
    st0 = [sum(durs[:i]) for i in range(len(durs))]
    try:
        R.mix_voice_music(aud, T, 'mix.wav', st0); aud = 'mix.wav'
    except Exception as e:
        print('music under voice failed, voice only:', e)
    # b-roll: one clip per spoken segment (hook + 3 beats), slow push-in, no repeats; the end card sits on a dark frame
    random.shuffle(clips)
    parts = []
    for i in range(len(segs) - 1):
        c = clips[i % len(clips)]; dur = durs[i]; out = 'sb_%d.mp4' % i
        R.sh(['ffmpeg', '-y', '-stream_loop', '-1', '-i', c, '-t', '%.3f' % dur, '-vf',
              "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0009,1.08)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=%d,eq=brightness=-0.04:saturation=0.9" % R.FPS,
              '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(R.FPS), out])
        parts.append(out)
    R.sh(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=0x0b1220:s=1080x1920:r=%d' % R.FPS, '-t', '%.3f' % durs[-1], '-c:v', 'libx264', '-pix_fmt', 'yuv420p', 'sb_end.mp4'])
    parts.append('sb_end.mp4')
    open('sb_list.txt', 'w').write(''.join("file '%s'\n" % p for p in parts))
    R.sh(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'sb_list.txt', '-c', 'copy', 'sb_all.mp4'])
    build_ass(segs, durs, wts, T, 'story.ass')
    R.sh(['ffmpeg', '-y', '-i', 'sb_all.mp4', '-i', aud, '-vf', 'ass=story.ass', '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
          '-c:a', 'aac', '-b:a', '160k', '-t', '%.2f' % T, '-movflags', '+faststart', 'out/latest.mp4'])
    dd = dict(d); dd.update({'hook': hook, 'points': beats, 'title': hook, 'series': 'BEHIND THE BUILD', 'cover_title': hook})
    try:
        R.sh(['ffmpeg', '-y', '-ss', '%.2f' % min(1.0, durs[0] / 2), '-i', 'sb_all.mp4', '-frames:v', '1', 'story_bg.jpg'])
        R.make_post_cover(dd, bg='story_bg.jpg')
    except Exception as e:
        print('story cover failed:', e); R.make_post_cover(dd)
    fallback = hook + '\n\n' + '\n'.join(beats) + '\n\nComment AUDIT and I will show you where your enquiries get stuck.\n\n#thecopygrind3r #automation #smallbusiness #aiautomation'
    cap = R.clean_caption(R.human_caption(dd, R.clean_caption(fallback)))
    json.dump({'date': d['date'], 'id': d['id'], 'caption': cap, 'caption_l1': cap.split('\n')[0][:120], 'audio_mode': 'voice', 'duration': T,
               'narrated': True, 'ai_clip': True, 'music': getattr(R, 'MUSIC_USED', None), 'mode': 'story', 'story_fact': fact,
               'cover': os.path.exists('out/cover.jpg'), 'hook_style': 'story', 'point_style': 'broll', 'word_synced': bool(wts)}, open('out/meta.json', 'w'))
    print('rendered story reel', round(T, 1), 's')
