"""thecopygrind3r print-on-demand design factory (runs free on GitHub Actions).

Gemini (Google Search) researches in-group phrases buyers in our niches actually say ->
independent grader removes weak / risky ones (trademarks, people, profanity) ->
Pillow renders print-ready transparent PNGs (4500x5400, dark-shirt + light-shirt versions) ->
listing CSV (title, 15 buyer-intent tags, description) -> pushed to the public pod-assets branch,
ready to upload to Redbubble / TeePublic / Amazon Merch.

Env: COUNT (designs per run, default 10), DRY_RUN=1 (render locally, no push), TEST=1 (no Gemini).
"""
import csv, json, os, re, shutil, subprocess, datetime, random
from product_factory import gemini, slugify, REPO

OUT = 'pod_out'
BRANCH = 'pod-assets'
W, H = 4500, 5400
DRY = os.environ.get('DRY_RUN') == '1'
TEST = os.environ.get('TEST') == '1'

NICHES = [
    ('tech_ai', 'people who build with AI and automation: no-code builders, prompt engineers, n8n/Make/Zapier users, developers, IT support'),
    ('real_estate', 'estate agents, letting agents, landlords, property managers, mortgage brokers (never use the word REALTOR, it is a trademark)'),
    ('small_business', 'solo founders, freelancers, small agency owners, copywriters, side hustlers, small shop owners'),
]

# words that make a design unsellable or risky (trademarks, brands, people)
BLOCK = re.compile(r"\b(realtor|realtors|chatgpt|openai|gpt|claude|gemini|anthropic|google|microsoft|excel|apple|iphone|"
                   r"zillow|rightmove|zapier|n8n|notion|slack|amazon|tesla|elon|musk|nike|disney|marvel|star wars|"
                   r"pokemon|netflix|linkedin|tiktok|instagram|youtube|meta|copilot|github|python|java|stack overflow|"
                   r"keep calm|just do it|fuck|shit|bitch|damn)\b", re.I)

SYSTEM = ('You write original text-only t-shirt and sticker slogans for print-on-demand marketplaces. '
          'Method (TRW strategic marketing): 1) market research first: find the exact phrases, frustrations and inside jokes '
          'this buyer says in their own words (forums, Reddit, comment sections, top-selling designs), 2) the design is an identity '
          'signal: the buyer buys it because it says who they are to people like them, 3) one razor-sharp idea per design, '
          'specific beats generic, no hype, 4) look at what top sellers do and why it works, then make something better and original. '
          'Never use brand names, trademarks, product names, famous people, characters, song lyrics, film quotes or existing slogans. '
          'No profanity. No em dashes. English.')


def research(niche, desc, n):
    prompt = f"""Niche: {desc}.
Use Google Search to study what text-based shirts and stickers sell for this buyer on Redbubble, TeePublic and Amazon Merch, and the
phrases these people actually use about their work (Reddit, forums, comments). Then invent {n} ORIGINAL slogans.
Rules: 2-8 words total, split into 1-4 short lines for stacking. Funny or proud, instantly understood by the buyer, a little obscure to
outsiders is good. Each must work as a gift (coworker, birthday, new job). No brand or product names at all.
Return JSON only:
{{"designs":[{{"lines":["LINE 1","LINE 2"],"accent_line":0,"style":"stack|terminal|badge","buyer":"who buys it","why":"why this buyer
laughs or feels proud, in their words","title":"marketplace title, 40-60 chars, buyer words first, e.g. Funny Property Manager Gift ...",
"tags":["15 tags, each 2-4 words, buyer-intent, e.g. landlord gift, property manager shirt"],"description":"2 sentences, plain, who it is
for and the occasion"}}]}}
style guide: terminal = reads like a command or code line (tech only); badge = short proud identity line; stack = everything else."""
    txt = gemini(prompt, SYSTEM, want_json=False, search=True, temp=0.9)
    m = re.search(r'\{[\s\S]*\}', txt or '')
    try:
        return json.loads(m.group(0))['designs']
    except Exception:
        return gemini('Convert this to the JSON format it describes, return only JSON:\n' + (txt or '')[:12000], want_json=True).get('designs', [])


def grade(designs, niche_desc):
    prompt = f"""You are a hard-to-impress print-on-demand buyer for this niche: {niche_desc}.
Score each slogan 1-10 on: would I (or someone buying a gift for me) actually pay EUR 20 for this on a shirt? Penalise generic,
cringe, too long, already-common slogans (e.g. 'Coffee then X', 'I paused my game', 'Keep calm'), anything with a brand, trademark,
person, character, quote, profanity, or that insults a group. Return JSON only:
{{"scores":[{{"i":0,"score":7,"risk":"none|trademark|common|offensive","note":"short"}}]}}
Slogans:\n""" + '\n'.join(f"{i}: {' / '.join(d.get('lines', []))}" for i, d in enumerate(designs))
    r = gemini(prompt, 'Independent reviewer. Honest and strict.', temp=0.2)
    return {s.get('i'): s for s in r.get('scores', [])}


# ---------------------------------------------------------------- render
FONTS = {
    'black': ['/usr/share/fonts/opentype/inter/Inter-Black.otf', '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf',
              '/usr/share/fonts/opentype/inter/Inter-Bold.otf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
    'mono': ['/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf'],
    'regular': ['/usr/share/fonts/opentype/inter/Inter-SemiBold.otf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
}
PALETTES = {  # (main, accent, muted) for dark shirts / light shirts
    'dark': [((255, 255, 255), (34, 211, 238), (148, 163, 184)), ((255, 255, 255), (250, 204, 21), (148, 163, 184)),
             ((255, 255, 255), (251, 146, 60), (148, 163, 184))],
    'light': [((17, 24, 39), (8, 145, 178), (71, 85, 105)), ((17, 24, 39), (202, 138, 4), (71, 85, 105)),
              ((17, 24, 39), (234, 88, 12), (71, 85, 105))],
}


def font(kind, size):
    from PIL import ImageFont
    for p in FONTS[kind]:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit_size(d, text, kind, maxw, maxh):
    lo, hi = 40, 1400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = font(kind, mid); b = d.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= maxw and b[3] - b[1] <= maxh: lo = mid
        else: hi = mid - 1
    return lo


def render(design, mode, pal_i, path):
    from PIL import Image, ImageDraw
    main, accent, muted = PALETTES[mode][pal_i % 3]
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lines = [l.strip() for l in design['lines'] if l.strip()][:4]
    style = design.get('style', 'stack'); acc = design.get('accent_line', 0)
    maxw = 3900
    if style == 'terminal':
        lines = [l if i else '$ ' + l.lower() if not l.startswith('$') else l for i, l in enumerate(lines)]
        size = min(fit_size(d, l + '_', 'mono', maxw, 700) for l in lines)
        f = font('mono', size); lh = int(size * 1.35)
        block_h = lh * len(lines); y = (H - block_h) // 2 - 300
        for i, l in enumerate(lines):
            col = accent if i == acc else main
            d.text((300, y), l, font=f, fill=col + (255,)); y += lh
        last = lines[-1]; x_end = 300 + d.textlength(last, font=f)
        d.rectangle([x_end + size * 0.15, y - lh + size * 0.12, x_end + size * 0.7, y - lh + size * 1.05], fill=accent + (255,))
    else:
        kind = 'black'; sizes = []
        for i, l in enumerate(lines):
            s = fit_size(d, l.upper(), kind, maxw, 1100 if len(lines) <= 2 else 850)
            sizes.append(s)
        # keep a clear hierarchy but not wildly different sizes
        top = max(sizes); sizes = [max(s, int(top * 0.45)) if s < top * 0.45 else s for s in sizes]
        sizes = [min(s, fit_size(d, lines[i].upper(), kind, maxw, 1100)) for i, s in enumerate(sizes)]
        gaps = [int(s * 0.18) for s in sizes]
        boxes = [d.textbbox((0, 0), l.upper(), font=font(kind, s)) for l, s in zip(lines, sizes)]
        total = sum(b[3] - b[1] for b in boxes) + sum(gaps[:-1])
        rule = style == 'badge'
        if rule: total += 2 * 260
        y = (H - total) // 2 - 250
        if rule:
            d.rectangle([W // 2 - 900, y, W // 2 + 900, y + 40], fill=accent + (255,)); y += 260
        for i, (l, s, b) in enumerate(zip(lines, sizes, boxes)):
            f = font(kind, s); tw = b[2] - b[0]
            col = accent if i == acc else main
            d.text(((W - tw) // 2 - b[0], y - b[1]), l.upper(), font=f, fill=col + (255,))
            y += (b[3] - b[1]) + gaps[i]
        if rule:
            y += 220; d.rectangle([W // 2 - 900, y, W // 2 + 900, y + 40], fill=accent + (255,))
    img.save(path, optimize=True)
    return img


def preview(img_dark, img_light, path):
    from PIL import Image
    tile = 900; out = Image.new('RGB', (tile * 2, int(tile * 1.2)), (255, 255, 255))
    for k, (im, bg) in enumerate(((img_dark, (17, 24, 39)), (img_light, (241, 245, 249)))):
        t = Image.new('RGB', (tile, int(tile * 1.2)), bg)
        small = im.resize((tile, int(tile * 1.2)))
        t.paste(small, (0, 0), small); out.paste(t, (k * tile, 0))
    out.save(path, quality=85)


def contact_sheet(previews, path):
    from PIL import Image
    if not previews: return
    cols = 2; tw, th = 900, 540
    rows = (len(previews) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * th), (255, 255, 255))
    for i, p in enumerate(previews):
        im = Image.open(p).resize((tw, th)); sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(path, quality=80)


# ---------------------------------------------------------------- push
def push(stamp):
    wt = 'pod_wt'; shutil.rmtree(wt, ignore_errors=True)
    tok = os.environ.get('GITHUB_TOKEN', '')
    url = f'https://x-access-token:{tok}@github.com/{REPO}.git' if tok else f'https://github.com/{REPO}.git'
    r = subprocess.run(['git', 'clone', '-q', '--depth', '1', '-b', BRANCH, url, wt], capture_output=True)
    if r.returncode != 0:
        os.makedirs(wt); subprocess.run(['git', 'init', '-q', '-b', BRANCH], cwd=wt, check=True)
        subprocess.run(['git', 'remote', 'add', 'origin', url], cwd=wt, check=True)
    shutil.copytree(OUT, os.path.join(wt, stamp), dirs_exist_ok=True)
    g = lambda *a: subprocess.run(['git', '-c', 'user.name=tcg', '-c', 'user.email=tcg@users.noreply.github.com', *a], cwd=wt, check=True, capture_output=True)
    g('add', '.'); g('commit', '-qm', 'pod designs ' + stamp); g('push', '-q', 'origin', 'HEAD:' + BRANCH)
    return f'https://github.com/{REPO}/tree/{BRANCH}/{stamp}'


def clean_tags(tags):
    out = []
    for t in tags or []:
        t = re.sub(r'[^a-z0-9 ]', '', str(t).lower()).strip()
        if t and not BLOCK.search(t) and t not in out and len(t.split()) <= 4: out.append(t)
    return out[:15]


def main():
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
    count = int(os.environ.get('COUNT', '10'))
    day = datetime.date.today().toordinal()
    order = NICHES[day % 3:] + NICHES[:day % 3]
    picked = []
    if TEST:
        picked = [dict(lines=['IT WORKED', 'IN THE TEST', 'ENVIRONMENT'], accent_line=2, style='stack', niche='tech_ai', title='Test', tags=['a b'], description='x', score=9),
                  dict(lines=['automate the boring', 'part'], accent_line=1, style='terminal', niche='tech_ai', title='Test2', tags=[], description='x', score=9),
                  dict(lines=['LANDLORD', 'ON CALL SINCE THE BOILER'], accent_line=0, style='badge', niche='real_estate', title='T3', tags=[], description='x', score=9)]
    else:
        per = max(4, count // 2)
        for key, desc in order:
            if len(picked) >= count: break
            try:
                ds = [d for d in research(key, desc, per + 4) if d.get('lines')]
            except Exception as e:
                print('research failed', key, e); continue
            ds = [d for d in ds if not BLOCK.search(' '.join(d['lines']) + ' ' + d.get('title', ''))
                  and '—' not in ' '.join(d['lines']) and 2 <= len(' '.join(d['lines']).split()) <= 9]
            if not ds: continue
            try:
                sc = grade(ds, desc)
            except Exception as e:
                print('grade failed', e); continue
            for i, d in enumerate(ds):
                s = sc.get(i, {})
                print(key, s.get('score'), s.get('risk'), ' / '.join(d['lines']), '|', s.get('note'))
                if (s.get('score') or 0) >= 8 and s.get('risk', 'none') == 'none':
                    d.update(niche=key, score=s.get('score')); picked.append(d)
        picked = picked[:count]
    rows, previews = [], []
    for n, d in enumerate(picked):
        slug = slugify(' '.join(d['lines']))[:50].strip('-')
        folder = os.path.join(OUT, slug); os.makedirs(folder, exist_ok=True)
        dark = render(d, 'dark', n, os.path.join(folder, 'for-dark-shirts.png'))
        light = render(d, 'light', n, os.path.join(folder, 'for-light-shirts.png'))
        pv = os.path.join(folder, 'preview.jpg'); preview(dark, light, pv); previews.append(pv)
        rows.append({'folder': slug, 'niche': d.get('niche'), 'score': d.get('score'), 'text': ' / '.join(d['lines']),
                     'title': d.get('title', '')[:60], 'tags': ', '.join(clean_tags(d.get('tags'))),
                     'description': d.get('description', '').replace('—', ',')[:300], 'buyer': d.get('buyer', ''), 'why': d.get('why', '')})
    contact_sheet(previews, os.path.join(OUT, 'contact_sheet.jpg'))
    with open(os.path.join(OUT, 'listings.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ['folder']); w.writeheader(); w.writerows(rows)
    print('designs:', len(rows))
    if rows and not DRY and not TEST:
        stamp = datetime.date.today().isoformat()
        print('pushed', push(stamp))


if __name__ == '__main__':
    main()
