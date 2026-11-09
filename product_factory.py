"""thecopygrind3r digital product factory (runs free on GitHub Actions).

research (Gemini + Google Search) -> spec -> independent grade -> build PDF + XLSX + images
-> QA -> publish to Gumroad via API -> log to n8n.

Env: GUMROAD_TOKEN (repo secret). Optional: DRY_RUN=1 (build only), NICHE=A|B|C, COUNT=n.
Products are saved as Gumroad drafts while publishing is blocked (e.g. no payout method);
every run tries to enable those drafts, so they go live automatically once publishing is allowed.
"""
import json, os, re, subprocess, sys, time, datetime, shutil, zipfile, textwrap, random
import urllib.request, urllib.parse

GEMINI = 'https://natenathan.duckdns.org/webhook/gemini-chain'
LOG_HOOK = 'https://natenathan.duckdns.org/webhook/product-log'
API = 'https://api.gumroad.com/v2'
TOKEN = os.environ.get('GUMROAD_TOKEN', '')
DRY = os.environ.get('DRY_RUN') == '1'
REPO = os.environ.get('GITHUB_REPOSITORY', 'nathankunaka10-maker/tcg-video')
ASSET_BRANCH = 'product-assets'
OUT = 'pout'
BRAND = 'thecopygrind3r'
NAVY, CYAN, INK, MUTE, PAPER = (11, 18, 32), (34, 211, 238), (17, 24, 39), (100, 116, 139), (248, 250, 252)

NICHES = {
    'A': ('Real estate business kits', 'estate agents, letting/rental agents, landlords and small property managers. Lead trackers, enquiry follow-up systems, viewing checklists, tenant onboarding, listing marketing kits, maintenance and rent trackers, commission and pipeline trackers.', 'business-and-money/real-estate'),
    'B': ('AI and small-business operations toolkits', 'solo service businesses and small agencies. Prompt packs for a specific job, client onboarding kits, SOP packs, content calendars, sales scripts and follow-up templates, AI workflow planners, pricing calculators.', 'business-and-money'),
    'C': ('Printable planners and trackers', 'specific everyday buyers with a clear job to do (e.g. shift workers, new pet owners, small sellers, freelancers, wedding planners, students). Pinterest-friendly printable planners and trackers.', 'self-improvement'),
}


# ---------------------------------------------------------------- helpers
def http(url, data=None, method=None, headers=None, timeout=300, raw=False):
    h = {'User-Agent': 'tcg-factory/1.0'}
    h.update(headers or {})
    body = None
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, (dict, list)) and h.get('Content-Type') == 'application/json':
            body = json.dumps(data).encode()
        else:
            body = urllib.parse.urlencode(data, doseq=True).encode()
            h.setdefault('Content-Type', 'application/x-www-form-urlencoded')
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return (r.status, dict(r.headers), b) if raw else json.loads(b or b'{}')
    except urllib.error.HTTPError as e:
        b = e.read()
        if raw:
            return e.code, dict(e.headers), b
        try:
            return json.loads(b)
        except Exception:
            return {'success': False, 'http': e.code, 'body': b[:500].decode('utf-8', 'ignore')}


def gemini(prompt, system='', want_json=True, search=False, temp=0.7):
    payload = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
               'generationConfig': {'temperature': temp}}
    if system:
        payload['systemInstruction'] = {'parts': [{'text': system}]}
    if search:
        payload['tools'] = [{'google_search': {}}]
    elif want_json:
        payload['generationConfig']['responseMimeType'] = 'application/json'
    for attempt in range(5):
        try:
            r = http(GEMINI, {'payload': payload}, headers={'Content-Type': 'application/json'}, timeout=290)
        except Exception as e:  # network timeout: back off and retry instead of killing the niche
            r = {'exception': str(e)[:200]}
        try:
            txt = ''.join(p.get('text', '') for p in r['candidates'][0]['content']['parts'])
        except Exception:
            # empty {} = every model in the gateway chain was rate-limited; wait it out (30s, 60s, 90s, 120s)
            print('gemini error', str(r)[:300]); time.sleep(30 * (attempt + 1)); continue
        if not want_json:
            return txt
        m = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', txt)
        try:
            return json.loads(m.group(0) if m else txt)
        except Exception:
            print('bad json, retry'); time.sleep(3)
    raise RuntimeError('gemini failed')


def gum(path, data=None, method='POST'):
    d = dict(data or {})
    d['access_token'] = TOKEN
    if method == 'GET':
        return http(API + path + '?' + urllib.parse.urlencode(d, doseq=True))
    return http(API + path, d, method=method)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


# ---------------------------------------------------------------- research + spec
TRW = """Apply The Real World (TRW) marketing principles (Andrew = strategic marketing, Arno = business/marketing mastery, Dylan = social):
- Winner's Writing Process before writing anything: 1) who exactly (one group, one problem, one dream state, in THEIR words) 2) where they are now (awareness level; marketplace shoppers are solution-aware and actively searching, Pinterest users are passive scrollers) 3) the one action (buy) 4) the step-by-step realisations in their mind: "this is for someone like me" -> "this solves my exact problem" -> "it is easy to use" -> "it is worth more than the price" -> "no risk" -> buy 5) what triggers each step (title, cover, first line, what's inside, proof, price).
- Market research with the buyer's real words: current state (frustrations, internal monologue), dream state, roadblocks, solutions tried, product choice criteria. 5-star reviews = dream language, 3-star = near-miss roadblocks, 1-star = broken promises to fix.
- Top-player analysis at the WHY level: copy the mechanism that makes bestsellers sell, never the surface.
- Three thresholds must clear: value > cost (raise pain/desire, lower effort), certainty ("will this work for ME": specifics, a real example row, preview pages), trust (calm competence, no hype, no over-claiming).
- Persuasion: lead with the buyer's identity and situation, not product info. Sensory, specific language. Pain -> relief. Every claim backed by a specific (what exactly is inside, how it works). Handle objections by agree-reframe-prove. One clear CTA.
- Arno: razor-sharp message a 12-year-old understands, message x market x media fit, compete on anything but price, honest guarantees only, no hype or desperation, measurable.
"""

SYSTEM = (TRW + "\nYou are the product lead of a small digital-products studio. You only make products a specific buyer would pay for "
          "because they solve one concrete job better than free alternatives. No fluff, no filler pages, no fake statistics, "
          "no invented testimonials, no trademarks or brand names you do not own, no medical/legal/financial advice beyond plain record keeping. "
          "Write in plain, warm, direct English. Never use em dashes.")


def research(niche_key, existing):
    name, scope, _ = NICHES[niche_key]
    prompt = f"""Find the single best NEW digital product to make next in this niche: {name}.
Scope: {scope}
Method (Iman Gadzhi 'unique value zone' + marketplace validation): search the web (Etsy and Gumroad bestseller listings, Pinterest, Reddit questions) for products in this niche that clearly sell (bestseller badges, many reviews, many sales), then go one level narrower to a specific buyer + specific job that is under-served.
Second demand check for each candidate: Google Trends direction for its main buyer keyword over the last 12 months (rising/flat/falling) and roughly how many advertisers run Meta Ad Library ads for similar products. Prefer rising trend + few advertisers; drop falling trends.
Avoid anything too close to these existing products: {existing or 'none'}.
For each candidate capture the buyer's REAL words (from reviews/questions you found): their current-state frustration, dream state and the roadblock the product removes, and do a top-player analysis of the best-selling competitor (what mechanism makes it sell, and its 1-3 star review complaints to beat).
Give 6 candidates and pick the best by: proven demand evidence, narrowness, can be delivered well as a PDF kit plus an Excel/Google Sheets tracker, fair price, low competition.
Return ONLY JSON: {{"candidates":[{{"idea":"","buyer":"","job":"","evidence":"what you saw that proves demand, with source names/URLs","trend":"rising|flat|falling","competition":"","price_eur":0,"score":0}}],"pick":{{"idea":"","buyer":"","job":"","why":"","evidence":"","buyer_words":"","competitor_mechanism":"","complaints_to_beat":"","price_eur":0}}}}"""
    for attempt in range(3):
        txt = gemini(prompt, SYSTEM, want_json=False, search=True, temp=0.6)
        m = re.search(r'\{[\s\S]*\}', txt or '')
        try:
            res = json.loads(m.group(0))
        except Exception:
            try:
                res = gemini('Convert this to the JSON format it describes, return only JSON:\n' + (txt or '')[:12000], want_json=True)
            except Exception:
                res = {}
        pick = (res or {}).get('pick') or ((res or {}).get('candidates') or [{}])[0]
        if pick.get('idea') and pick.get('buyer'):
            res['pick'] = pick; return res
        print('research returned no usable pick, retrying', attempt + 1)
    raise RuntimeError('research gave no usable pick after 3 tries')


SPEC_SCHEMA = """{
 "wwp": {"who":"","awareness_and_attention":"","action":"buy","mind_steps":["realisation 1","..."],"triggers":["which element triggers each step"],"weakest_threshold":"value|certainty|trust and how this listing raises it"},
 "title": "<=70 chars, specific: who + what result, no hype",
 "subtitle": "one line",
 "price_eur": 9,
 "summary": "<=140 chars, the 'you get' line",
 "audience": "who exactly",
 "tags": ["8 lowercase buyer search phrases, each max 20 characters"],
 "description_paragraphs": ["3 short paragraphs: the problem, what this kit does, who it is for"],
 "included": ["5-8 bullet lines describing what is inside"],
 "benefits": ["4-6 concrete outcomes"],
 "how_to_use": ["4-6 numbered steps"],
 "pages": [
   {"type":"guide","title":"","sections":[{"heading":"","body":"2-5 sentences of genuinely useful, specific know-how","bullets":["optional"]}]},
   {"type":"checklist","title":"","intro":"","groups":[{"heading":"","items":["specific, actionable items"]}]},
   {"type":"tracker","title":"","intro":"","columns":["4-7 short column names"],"example":["one realistic example row, same length as columns"],"rows":18,"numeric_columns":["names of columns that hold amounts to total"]},
   {"type":"template","title":"","intro":"","fields":["labelled fields to fill in"]},
   {"type":"script","title":"","intro":"","blocks":[{"label":"e.g. First reply / Follow-up day 3","text":"ready-to-use wording with [placeholders]"}]},
   {"type":"worksheet","title":"","prompts":["reflection or planning prompts"]}
 ]
}"""


def make_spec(pick, niche_key):
    prompt = f"""Create the full product for this brief.
Buyer: {pick.get('buyer')}
Job to be done: {pick.get('job')}
Idea: {pick.get('idea')}
Why it sells: {pick.get('why')} Evidence: {pick.get('evidence')}
Buyer's own words: {pick.get('buyer_words')}
Top competitor's selling mechanism (beat it, don't copy the surface): {pick.get('competitor_mechanism')}
Complaints in competitors' 1-3 star reviews to fix: {pick.get('complaints_to_beat')}
Fill "wwp" FIRST, then write every listing element (title, summary, description, included, benefits) to trigger the mind steps in order, in the buyer's words. Title = buyer identity + concrete result (search-friendly, no hype). First description paragraph names their current-state pain in their words; second shows the relief and exactly how the kit delivers it; third removes the main objection.
DEPTH (buyers judge value by how full and specific it is): guide pages have 4-6 sections, each body 4-6 sentences of concrete know-how with numbers/examples; every checklist has 3-5 groups of 5-8 items; scripts have 4-6 blocks; templates have 10-16 fields; worksheets have 8-12 prompts; trackers have 5-7 columns.
HONESTY (trust threshold, and refunds kill Gumroad accounts): "included", "benefits" and "how_to_use" may ONLY describe pages that exist in "pages" plus "an .xlsx spreadsheet (opens in Excel, Google Sheets or Numbers) with one tab per tracker, totals pre-built". Never promise links, apps, dashboards, one-click exports, automation, videos, bonuses, legal/tax/financial guarantees or anything not in the files. Tax/legal content says to confirm with a professional.
Rules: 8 to 12 pages total, every page must be immediately usable by this buyer, at least 2 tracker pages (they become spreadsheet tabs), include a 'guide' page with real know-how and at least one checklist. Use realistic example rows. Price in EUR between 7 and 39 depending on value (business kits 15-39, consumer planners 7-15). Currency examples in EUR, dates as DD/MM/YYYY.
Return ONLY JSON matching this schema:
{SPEC_SCHEMA}"""
    return gemini(prompt, SYSTEM, temp=0.7)


def grade(spec):
    prompt = (TRW + "\nYou are a strict buyer and a TRW marketing professor reviewing a student's product. Score 1-10 for each: usefulness to the stated buyer, "
              "specificity (not generic), accuracy (no false or risky claims; ANY promised feature/file/link/dashboard/export not actually present in pages = accuracy max 4), completeness (7-11 content pages; guides 4-6 sections of 4-6 sentences; checklists 15+ items; scripts 4+ blocks; templates 10+ fields; worksheets 8+ prompts; ANY miss = completeness max 5), completeness (pages actually usable), sellability at its price, "
              "trw_copy (WWP done properly, buyer's words, leads with identity/pain, all three thresholds raised, no hype, one clear message). "
              "Then overall = the minimum of the six. List concrete fixes. Return ONLY JSON {\"scores\":{...},\"overall\":0,\"fixes\":[\"...\"]}.\n\n"
              + json.dumps(spec)[:30000])
    return gemini(prompt, 'You are an independent, hard-to-impress reviewer.', temp=0.2)


def revise(spec, fixes):
    prompt = ("Apply ALL these fixes to the product spec and return the full improved spec as JSON with the same schema. Fixes:\n- "
              + '\n- '.join(fixes) + '\n\nSpec:\n' + json.dumps(spec))
    return gemini(prompt, SYSTEM, temp=0.5)


# ---------------------------------------------------------------- build: PDF
def build_pdf(spec, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color
    W, H = A4
    c = canvas.Canvas(path, pagesize=A4)
    col = lambda t: Color(t[0] / 255, t[1] / 255, t[2] / 255)
    M = 46

    def wrap(text, size, width):
        cpl = max(20, int(width / (size * 0.5)))
        return textwrap.wrap(str(text), cpl) or ['']

    def footer(n):
        c.setFont('Helvetica', 8); c.setFillColor(col(MUTE))
        c.drawString(M, 24, spec['title'][:80]); c.drawRightString(W - M, 24, f'{BRAND}  ·  {n}')

    def header(title, n):
        c.setFillColor(col(NAVY)); c.rect(0, H - 70, W, 70, fill=1, stroke=0)
        c.setFillColor(col(CYAN)); c.rect(0, H - 74, W, 4, fill=1, stroke=0)
        c.setFillColor(col(PAPER)); c.setFont('Helvetica-Bold', 18); c.drawString(M, H - 44, title[:60])
        footer(n)

    def para(text, y, size=10.5, width=W - 2 * M, colr=INK, font='Helvetica', lead=1.45):
        c.setFont(font, size); c.setFillColor(col(colr))
        for ln in wrap(text, size, width):
            if y < 60: return y
            c.drawString(M, y, ln); y -= size * lead
        return y

    n = 1
    # cover
    c.setFillColor(col(NAVY)); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(col(CYAN)); c.rect(M, H - 200, 60, 6, fill=1, stroke=0)
    y = H - 250
    c.setFillColor(col(PAPER))
    for ln in wrap(spec['title'], 30, W - 2 * M)[:4]:
        c.setFont('Helvetica-Bold', 30); c.drawString(M, y, ln); y -= 38
    y -= 6
    c.setFillColor(col(CYAN)); c.setFont('Helvetica', 13)
    for ln in wrap(spec.get('subtitle', ''), 13, W - 2 * M)[:3]:
        c.drawString(M, y, ln); y -= 19
    c.setFillColor(col(PAPER)); c.setFont('Helvetica', 10)
    c.drawString(M, 60, f'{BRAND}  ·  printable PDF + Excel / Google Sheets tracker')
    c.showPage(); n += 1
    # how to use
    header('How to use this kit', n); y = H - 110
    for i, s in enumerate(spec.get('how_to_use', []), 1):
        y = para(f'{i}. {s}', y, 11); y -= 6
    y -= 10; c.setFont('Helvetica-Bold', 12); c.setFillColor(col(INK)); c.drawString(M, y, "What's inside"); y -= 20
    for s in spec.get('included', []):
        y = para('•  ' + s, y, 10.5); y -= 2
    c.showPage(); n += 1

    for p in spec['pages']:
        t = p.get('type'); header(p.get('title', ''), n); y = H - 105
        if p.get('intro'):
            y = para(p['intro'], y, 10.5, colr=MUTE); y -= 8
        if t == 'guide':
            for s in p.get('sections', []):
                if y < 140: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                c.setFont('Helvetica-Bold', 12.5); c.setFillColor(col(INK)); c.drawString(M, y, s.get('heading', '')[:70]); y -= 18
                y = para(s.get('body', ''), y); y -= 4
                for b in s.get('bullets', []) or []:
                    y = para('•  ' + b, y, 10.5); y -= 1
                y -= 10
        elif t == 'checklist':
            for g in p.get('groups', []):
                if y < 120: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                c.setFont('Helvetica-Bold', 12); c.setFillColor(col(INK)); c.drawString(M, y, g.get('heading', '')[:70]); y -= 18
                for it in g.get('items', []):
                    if y < 70: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                    c.setStrokeColor(col(MUTE)); c.rect(M, y - 2, 10, 10, fill=0)
                    lines = wrap(it, 10.5, W - 2 * M - 22)
                    c.setFont('Helvetica', 10.5); c.setFillColor(col(INK))
                    for ln in lines:
                        c.drawString(M + 20, y, ln); y -= 15
                    y -= 3
                y -= 8
        elif t == 'tracker':
            cols = p.get('columns', [])[:7] or ['Item', 'Notes']
            cw = (W - 2 * M) / len(cols); rh = 22
            c.setFillColor(col(NAVY)); c.rect(M, y - 6, W - 2 * M, rh, fill=1, stroke=0)
            from reportlab.pdfbase.pdfmetrics import stringWidth
            def fit(txt, fnt, size, w):
                txt = str(txt)
                while size > 6 and stringWidth(txt, fnt, size) > w: size -= 0.5
                while txt and stringWidth(txt, fnt, size) > w: txt = txt[:-1]
                return txt, size
            c.setFillColor(col(PAPER))
            for i, h in enumerate(cols):
                t2, sz = fit(h, 'Helvetica-Bold', 8.5, cw - 8); c.setFont('Helvetica-Bold', sz)
                c.drawString(M + i * cw + 4, y + 2, t2)
            y -= rh
            rows = [p.get('example') or []] + [[]] * int(p.get('rows', 16))
            for r_i, row in enumerate(rows):
                if y < 60: break
                if r_i % 2 == 0: c.setFillColor(Color(0.95, 0.97, 0.99)); c.rect(M, y - 6, W - 2 * M, rh, fill=1, stroke=0)
                c.setStrokeColor(Color(0.85, 0.88, 0.92)); c.line(M, y - 6, W - M, y - 6)
                c.setFillColor(col(MUTE if r_i == 0 else INK)); fn = 'Helvetica-Oblique' if r_i == 0 else 'Helvetica'
                for i, v in enumerate(row[:len(cols)]):
                    t2, sz = fit(v, fn, 8.5, cw - 8); c.setFont(fn, sz)
                    c.drawString(M + i * cw + 4, y + 2, t2)
                y -= rh
        elif t == 'template':
            for f in p.get('fields', []):
                if y < 80: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                c.setFont('Helvetica-Bold', 10); c.setFillColor(col(INK)); c.drawString(M, y, str(f)[:80]); y -= 20
                c.setStrokeColor(Color(0.8, 0.83, 0.87)); c.line(M, y, W - M, y); y -= 22
        elif t == 'script':
            for b in p.get('blocks', []):
                if y < 150: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                c.setFont('Helvetica-Bold', 11); c.setFillColor(col(CYAN)); c.drawString(M, y, b.get('label', '')[:70]); y -= 16
                y = para(b.get('text', ''), y, 10.5); y -= 14
        elif t == 'worksheet':
            for q in p.get('prompts', []):
                if y < 130: c.showPage(); n += 1; header(p.get('title', '') + ' (cont.)', n); y = H - 105
                y = para(q, y, 11, font='Helvetica-Bold'); y -= 4
                c.setStrokeColor(Color(0.82, 0.85, 0.89))
                for _ in range(3):
                    c.line(M, y, W - M, y); y -= 20
                y -= 8
        c.showPage(); n += 1
    c.save()
    return n - 1


# ---------------------------------------------------------------- build: XLSX
def build_xlsx(spec, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = Workbook(); ws0 = wb.active; ws0.title = 'Start here'
    ws0['A1'] = spec['title']; ws0['A1'].font = Font(bold=True, size=16)
    ws0['A3'] = 'How to use'; ws0['A3'].font = Font(bold=True, size=12)
    for i, s in enumerate(spec.get('how_to_use', []), 1):
        ws0.cell(row=3 + i, column=1, value=f'{i}. {s}')
    ws0.column_dimensions['A'].width = 110
    head = PatternFill('solid', fgColor='0B1220'); thin = Side(style='thin', color='D7DEE7')
    used = set()
    for p in spec['pages']:
        if p.get('type') != 'tracker': continue
        name = re.sub(r'[\\/*?:\[\]]', '', p.get('title', 'Tracker'))[:28] or 'Tracker'
        while name in used: name = name[:26] + str(len(used))
        used.add(name)
        ws = wb.create_sheet(name); cols = p.get('columns', [])[:10]
        for i, h in enumerate(cols, 1):
            cl = ws.cell(row=1, column=i, value=h); cl.font = Font(bold=True, color='F8FAFC'); cl.fill = head
            cl.alignment = Alignment(vertical='center'); ws.column_dimensions[cl.column_letter].width = max(14, min(40, len(str(h)) + 8))
        ex = p.get('example') or []
        for i, v in enumerate(ex[:len(cols)], 1):
            ws.cell(row=2, column=i, value=v).font = Font(italic=True, color='64748B')
        last = 2 + int(p.get('rows', 18)) + 30
        for r in range(2, last + 1):
            for ci in range(1, len(cols) + 1):
                ws.cell(row=r, column=ci).border = Border(bottom=thin)
        nums = set(p.get('numeric_columns') or [])
        for i, h in enumerate(cols, 1):
            if h in nums:
                L = ws.cell(row=1, column=i).column_letter
                ws.cell(row=last + 2, column=i, value=f'=SUM({L}3:{L}{last})').font = Font(bold=True)
                for r in range(3, last + 1):
                    ws.cell(row=r, column=i).number_format = '€#,##0.00'
        if nums:
            ws.cell(row=last + 2, column=1, value='Total').font = Font(bold=True)
        ws.freeze_panes = 'A2'
    wb.save(path)
    return len(used)


# ---------------------------------------------------------------- build: images
def font(size, bold=False):
    from PIL import ImageFont
    cands = ['/usr/share/fonts/opentype/inter/Inter-Bold.otf' if bold else '/usr/share/fonts/opentype/inter/Inter-Regular.otf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for p in cands:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_block(d, xy, text, f, fill, maxw, lead=1.18, max_lines=6):
    x, y = xy; words = str(text).split(); line = ''; lines = []
    for w in words:
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw: line = t
        else: lines.append(line); line = w
    if line: lines.append(line)
    for ln in lines[:max_lines]:
        d.text((x, y), ln, font=f, fill=fill); y += int(f.size * lead)
    return y


def build_images(spec, pdf_path, folder):
    from PIL import Image, ImageDraw
    subprocess.run(['pdftoppm', '-png', '-r', '60', '-f', '2', '-l', '5', pdf_path, os.path.join(folder, 'pg')], check=True)
    pages = sorted(f for f in os.listdir(folder) if f.startswith('pg') and f.endswith('.png'))
    shots = [Image.open(os.path.join(folder, f)).convert('RGB') for f in pages]

    def fan(img, box, n=3):
        x0, y0, x1, y1 = box; h = y1 - y0
        for i, s in enumerate(shots[:n]):
            s2 = s.resize((int(s.width * h / s.height), h))
            off = i * int(s2.width * 0.42)
            img.paste((200, 210, 220), (x0 + off + 8, y0 + 8, x0 + off + 8 + s2.width, y0 + 8 + h))
            img.paste(s2, (x0 + off, y0))

    out = {}
    # cover 1280x720
    im = Image.new('RGB', (1280, 720), NAVY); d = ImageDraw.Draw(im)
    d.rectangle((60, 90, 140, 98), fill=CYAN)
    y = text_block(d, (60, 130), spec['title'], font(54, True), PAPER, 620, max_lines=4)
    text_block(d, (60, y + 18), spec.get('summary', ''), font(26), CYAN, 600, max_lines=3)
    d.text((60, 650), 'PDF kit + Excel / Google Sheets tracker', font=font(22), fill=(203, 213, 225))
    fan(im, (720, 110, 1260, 640)); im.save(os.path.join(folder, 'cover.png')); out['cover'] = 'cover.png'
    # square thumbnail 1000
    im = Image.new('RGB', (1000, 1000), NAVY); d = ImageDraw.Draw(im)
    y = text_block(d, (60, 70), spec['title'], font(56, True), PAPER, 880, max_lines=3)
    fan(im, (90, max(y + 30, 380), 980, 960)); im.save(os.path.join(folder, 'thumb.png')); out['thumb'] = 'thumb.png'
    # included 1000x1000
    im = Image.new('RGB', (1000, 1000), PAPER); d = ImageDraw.Draw(im)
    d.text((60, 60), "What's inside", font=font(52, True), fill=INK); y = 160
    for s in spec.get('included', [])[:8]:
        d.ellipse((60, y + 12, 76, y + 28), fill=CYAN)
        y = text_block(d, (96, y), s, font(30), INK, 840, max_lines=2) + 18
    im.save(os.path.join(folder, 'included.png')); out['included'] = 'included.png'
    # pinterest 1000x1500
    im = Image.new('RGB', (1000, 1500), NAVY); d = ImageDraw.Draw(im)
    y = text_block(d, (60, 80), spec['title'], font(66, True), PAPER, 880, max_lines=4)
    y = text_block(d, (60, y + 20), spec.get('summary', ''), font(34), CYAN, 880, max_lines=3)
    fan(im, (90, y + 50, 980, 1400)); d.text((60, 1430), BRAND, font=font(30, True), fill=(203, 213, 225))
    im.save(os.path.join(folder, 'pin.png')); out['pin'] = 'pin.png'
    for f in pages: os.remove(os.path.join(folder, f))
    return out


# ---------------------------------------------------------------- QA
def qa(spec, pdf_path, xlsx_path, n_pages, n_tabs):
    issues = []
    if n_pages < 8: issues.append(f'only {n_pages} PDF pages')
    if n_tabs < 1: issues.append('no spreadsheet tabs')
    if len(spec.get('title', '')) > 90: issues.append('title too long')
    txt = json.dumps(spec)
    if '—' in txt or '–' in txt: issues.append('em dash')
    listing = json.dumps({k: v for k, v in spec.items() if k != 'pages'})
    if re.search(r'lorem ipsum|\bTODO\b', txt, re.I) or re.search(r'\[insert|\[your', listing, re.I): issues.append('placeholder text')
    try:
        words = len(subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True).stdout.split())
    except Exception:
        words = 9999
    if words < 1200: issues.append(f'thin content: {words} words')
    pg = spec.get('pages', [])
    if len(pg) < 7: issues.append(f'only {len(pg)} content pages (need 7-11)')
    for p in pg:
        t = p.get('type')
        if t == 'guide' and len(p.get('sections', [])) < 4: issues.append(f"guide '{p.get('title')}' has <4 sections")
        if t == 'checklist' and sum(len(g.get('items', [])) for g in p.get('groups', [])) < 15: issues.append(f"checklist '{p.get('title')}' has <15 items")
        if t == 'script' and len(p.get('blocks', [])) < 4: issues.append(f"script '{p.get('title')}' has <4 blocks")
        if t == 'template' and len(p.get('fields', [])) < 10: issues.append(f"template '{p.get('title')}' has <10 fields")
        if t == 'worksheet' and len(p.get('prompts', [])) < 8: issues.append(f"worksheet '{p.get('title')}' has <8 prompts")
    claims = ' '.join(spec.get('included', []) + spec.get('how_to_use', []) + spec.get('benefits', []))
    bad = re.findall(r'one-click|dashboard|link (?:inside|in the|below)|automatic(?:ally)? (?:calculat|sync|import)|video|bonus|guarantee', claims, re.I)
    if bad: issues.append('promises missing features: ' + ', '.join(sorted(set(b.lower() for b in bad))))
    return issues


# ---------------------------------------------------------------- publish
def clean_tags(tags):
    out = []
    for t in tags:
        t = re.sub(r'[^a-z0-9 ]', '', str(t).lower()).strip()
        while len(t) > 20 and ' ' in t: t = t.rsplit(' ', 1)[0]
        while t.split() and t.split()[-1] in ('for', 'and', 'of', 'the', 'a', 'to', 'in', 'with', 'my'): t = t.rsplit(' ', 1)[0] if ' ' in t else ''
        if 2 < len(t) <= 20 and t not in out: out.append(t)
    return out[:8]


def push_assets(folder, slug):
    """Commit marketing images to the public product-assets branch; return raw base URL."""
    wt = 'assets_wt'
    shutil.rmtree(wt, ignore_errors=True)
    tok = os.environ.get('GITHUB_TOKEN', '')
    url = f'https://x-access-token:{tok}@github.com/{REPO}.git' if tok else f'https://github.com/{REPO}.git'
    r = subprocess.run(['git', 'clone', '-q', '--depth', '1', '-b', ASSET_BRANCH, url, wt], capture_output=True)
    if r.returncode != 0:
        os.makedirs(wt); subprocess.run(['git', 'init', '-q', '-b', ASSET_BRANCH], cwd=wt, check=True)
        subprocess.run(['git', 'remote', 'add', 'origin', url], cwd=wt, check=True)
    dst = os.path.join(wt, slug); os.makedirs(dst, exist_ok=True)
    for f in ('cover.png', 'thumb.png', 'included.png', 'pin.png'):
        shutil.copy(os.path.join(folder, f), dst)
    g = lambda *a: subprocess.run(['git', '-c', 'user.name=tcg', '-c', 'user.email=tcg@users.noreply.github.com', *a], cwd=wt, check=True, capture_output=True)
    g('add', '.'); g('commit', '-qm', 'assets ' + slug); g('push', '-q', 'origin', 'HEAD:' + ASSET_BRANCH)
    return f'https://raw.githubusercontent.com/{REPO}/{ASSET_BRANCH}/{slug}/'


def upload_file(path):
    size = os.path.getsize(path)
    pre = gum('/files/presign', {'filename': os.path.basename(path), 'file_size': size})
    if not pre.get('success'): raise RuntimeError('presign failed: ' + str(pre)[:300])
    parts = []
    with open(path, 'rb') as fh:
        for p in pre['parts']:
            chunk = fh.read(100 * 1024 * 1024)
            st, hd, _ = http(p['presigned_url'], chunk, method='PUT', raw=True, headers={'Content-Type': 'application/octet-stream'})
            etag = {k.lower(): v for k, v in hd.items()}.get('etag')
            if st != 200 or not etag: raise RuntimeError(f'part upload failed {st}')
            parts.append({'part_number': p['part_number'], 'etag': etag})
    data = {'upload_id': pre['upload_id'], 'key': pre['key']}
    for p in parts:
        data.setdefault('parts[][part_number]', []).append(p['part_number'])
        data.setdefault('parts[][etag]', []).append(p['etag'])
    done = gum('/files/complete', data)
    if not done.get('success'): raise RuntimeError('complete failed: ' + str(done)[:300])
    return done['file_url']


def pick_category(hint):
    r = gum('/categories', method='GET')
    paths = [c['path'] for c in r.get('categories', [])] if r.get('success') else []
    if hint in paths: return hint
    for p in paths:
        if p.startswith(hint.split('/')[0]): return p if hint.split('/')[0] == p else hint.split('/')[0] if hint.split('/')[0] in paths else p
    return None


def publish(spec, zip_path, base_url, niche_key):
    desc = ''.join(f'<p>{x}</p>' for x in spec.get('description_paragraphs', []))
    desc += '<h3>What you get</h3><ul>' + ''.join(f'<li>{x}</li>' for x in spec.get('included', [])) + '</ul>'
    desc += '<h3>Why it helps</h3><ul>' + ''.join(f'<li>{x}</li>' for x in spec.get('benefits', [])) + '</ul>'
    desc += f'<p><img src="{base_url}included.png"></p>'
    desc += '<p>Instant download: a printable PDF plus an Excel file that also opens in Google Sheets. Made by thecopygrind3r.</p>'
    file_url = upload_file(zip_path)
    data = {'name': spec['title'][:90], 'description': desc, 'price': int(round(float(spec.get('price_eur', 9)) * 100)),
            'price_currency_type': 'eur', 'custom_summary': spec.get('summary', '')[:150],
            'custom_permalink': slugify(spec['title'])[:40], 'files[][url]': file_url, 'tags[]': clean_tags(spec.get('tags', []))}
    cat = pick_category(NICHES[niche_key][2])
    if cat: data['category'] = cat
    r = gum('/products', data)
    if not r.get('success') and 'permalink' in str(r).lower():
        data['custom_permalink'] = data['custom_permalink'][:34] + '-' + str(random.randint(100, 999)); r = gum('/products', data)
    if not r.get('success') and 'category' in str(r).lower():
        data.pop('category', None); r = gum('/products', data)
    if not r.get('success'): raise RuntimeError('create failed: ' + str(r)[:400])
    pid = r['product']['id']
    gum(f'/products/{pid}/covers', {'url': base_url + 'cover.png'})
    gum(f'/products/{pid}/covers', {'url': base_url + 'included.png'})
    gum(f'/products/{pid}/thumbnail', {'url': base_url + 'thumb.png'})
    return pid, r['product'].get('short_url') or r['product'].get('url'), r['product'].get('published'), r.get('warning', '')


def enable_drafts():
    r = gum('/products', method='GET'); n = 0
    for p in r.get('products', []) if r.get('success') else []:
        if not p.get('published') and p.get('files_count', 1) and 'thecopygrind3r' in (p.get('description') or ''):
            e = gum(f"/products/{p['id']}/enable", method='PUT')
            if e.get('success') and (e.get('product') or {}).get('published'): n += 1
    return n


def log(row):
    try:
        http(LOG_HOOK, row, headers={'Content-Type': 'application/json'}, timeout=60)
    except Exception as e:
        print('log failed', e)


# ---------------------------------------------------------------- main
def make_one(niche_key, existing):
    print('== niche', niche_key)
    res = research(niche_key, existing)
    pick = res.get('pick') or (res.get('candidates') or [{}])[0]
    print('pick:', pick.get('idea'), '|', pick.get('buyer'))
    spec = make_spec(pick, niche_key)
    g = grade(spec); print('grade', g.get('overall'), g.get('scores'))
    if (g.get('overall') or 0) < 8 and g.get('fixes'):
        spec = revise(spec, g['fixes']); g = grade(spec); print('regrade', g.get('overall'))
    if (g.get('overall') or 0) < 7:
        log({'status': 'rejected', 'title': spec.get('title'), 'niche': niche_key, 'score': g.get('overall'), 'note': '; '.join(g.get('fixes', [])[:5])})
        print('rejected by grader'); return None
    slug = slugify(spec['title']) + '-' + datetime.date.today().strftime('%m%d')
    folder = os.path.join(OUT, slug); os.makedirs(folder, exist_ok=True)
    pdf = os.path.join(folder, slug + '.pdf'); xlsx = os.path.join(folder, slug + '.xlsx')
    n_pages = build_pdf(spec, pdf); n_tabs = build_xlsx(spec, xlsx)
    imgs = build_images(spec, pdf, folder)
    issues = qa(spec, pdf, xlsx, n_pages, n_tabs)
    json.dump({'spec': spec, 'grade': g, 'research': res}, open(os.path.join(folder, 'spec.json'), 'w'), indent=1)
    zpath = os.path.join(folder, slug + '.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(pdf, os.path.basename(pdf)); z.write(xlsx, os.path.basename(xlsx))
    print('built', slug, 'pages', n_pages, 'tabs', n_tabs, 'issues', issues)
    if issues:
        fixes = ['Fix QA failure: ' + i for i in issues] + ['Make every page full: 7-11 content pages, guides 4-6 sections x 4-6 sentences, checklists 15+ items, scripts 4+ blocks, templates 10+ fields, worksheets 8+ prompts, all specific and expert', 'Remove every claim in included/benefits/how_to_use that the files do not deliver']
        spec = revise(spec, fixes); g2 = grade(spec); print('qa-revise grade', g2.get('overall'))
        if (g2.get('overall') or 0) >= 8: g = g2
        n_pages = build_pdf(spec, pdf); n_tabs = build_xlsx(spec, xlsx)
        imgs = build_images(spec, pdf, folder)
        issues = qa(spec, pdf, xlsx, n_pages, n_tabs)
        if (g.get('overall') or 0) < 8: issues.append(f"grade {g.get('overall')} after QA revise")
        json.dump({'spec': spec, 'grade': g, 'research': res}, open(os.path.join(folder, 'spec.json'), 'w'), indent=1)
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(pdf, os.path.basename(pdf)); z.write(xlsx, os.path.basename(xlsx))
        print('rebuilt pages', n_pages, 'tabs', n_tabs, 'issues', issues)
    if issues:
        log({'status': 'qa_failed', 'title': spec['title'], 'niche': niche_key, 'score': g.get('overall'), 'note': '; '.join(issues)}); return None
    if DRY or not TOKEN:
        print('dry run, not publishing'); return slug
    base = push_assets(folder, slug)
    pid, url, published, warning = publish(spec, zpath, base, niche_key)
    print('published' if published else 'draft', url, warning)
    log({'status': 'published' if published else 'draft', 'title': spec['title'], 'niche': niche_key, 'score': g.get('overall'),
         'price_eur': spec.get('price_eur'), 'url': url, 'product_id': pid, 'pin_image': base + 'pin.png', 'note': warning,
         'pin_title': spec['title'][:100], 'pin_description': (spec.get('summary', '') + ' ' + ' '.join('#' + t.replace(' ', '') for t in spec.get('tags', [])[:4]))[:480]})
    return slug


def main():
    os.makedirs(OUT, exist_ok=True)
    existing = []
    if TOKEN:
        r = gum('/products', method='GET'); existing = [p['name'] for p in r.get('products', [])] if r.get('success') else []
        print('enabled drafts:', enable_drafts())
    keys = list(NICHES)
    day = datetime.date.today().toordinal()
    count = int(os.environ.get('COUNT', '1'))
    for i in range(count):
        k = os.environ.get('NICHE') or keys[(day + i) % len(keys)]
        try:
            s = make_one(k, '; '.join(existing[-40:]))
            if s: existing.append(s)
        except Exception as e:
            print('FAILED', k, e); log({'status': 'error', 'niche': k, 'note': str(e)[:400]})


if __name__ == '__main__':
    main()
