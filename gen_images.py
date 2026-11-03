"""Daily free AI images for today's posts (HF ZeroGPU spaces). Composes branded covers with our own readable headline.
Outputs assets/gen/<ID>_<kind>.jpg. Fails soft: publishers fall back to text slides when a file is missing."""
import os, json, shutil, textwrap, urllib.request, glob, time
from gradio_client import Client, handle_file
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FEED = 'https://natenathan.duckdns.org/webhook/today-posts'
PHOTO = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
OUT = 'assets/gen'
tok = os.environ.get('HF_TOKEN') or None
os.makedirs(OUT, exist_ok=True)

def client(space):
    try: return Client(space, token=tok)
    except TypeError: return Client(space, hf_token=tok)

def first_path(r):
    p = r[0] if isinstance(r, (list, tuple)) else r
    for _ in range(4):
        if isinstance(p, (list, tuple)): p = p[0]
        elif isinstance(p, dict): p = p.get('image') or p.get('path') or p.get('url')
        else: break
    return p

def gen_klein(prompt, person, w, h):
    c = client('black-forest-labs/flux-3-image-klein')
    imgs = [{'image': handle_file(PHOTO), 'caption': None}] if person else []
    scale = 1152 / max(w, h)
    return first_path(c.predict(prompt=prompt, input_images=imgs, width=int(w * scale) // 16 * 16, height=int(h * scale) // 16 * 16, api_name='/generate'))

def gen_zimage(prompt, w, h):
    c = client('Tongyi-MAI/Z-Image-Turbo')
    res = '864x1152 ( 3:4 )' if h > w * 1.1 else '1024x1024 ( 1:1 )'
    if h > w * 1.5: res = '720x1280 ( 9:16 )'
    return first_path(c.predict(prompt=prompt, resolution=res, api_name='/generate'))

def fill(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s + 1), int(img.height * s + 1)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))

def font(size):
    for f in ['/usr/share/fonts/truetype/inter/Inter-Black.ttf', '/usr/share/fonts/opentype/inter/Inter-Black.otf', '/usr/share/fonts/truetype/inter/Inter-ExtraBold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if os.path.exists(f): return ImageFont.truetype(f, size)
    hits = glob.glob('/usr/share/fonts/**/Inter*Black*', recursive=True) + glob.glob('/usr/share/fonts/**/Inter*Bold*', recursive=True)
    return ImageFont.truetype(hits[0], size) if hits else ImageFont.load_default()

def compose(src, item):
    """Save the raw faceless photo, then put the fixed branded cover frame on top (cover.py)."""
    from cover import make_cover, short_title
    w, h = item['w'], item['h']
    img = fill(Image.open(src).convert('RGB'), w, h)
    bgp = '%s/%s_%s_bg.jpg' % (OUT, item['id'], item['kind'])
    img.save(bgp, quality=90)
    title = (item.get('cover_title') or '').strip() or short_title(item.get('text') or item.get('topic') or '')
    json.dump({'cover_title': title, 'series': item.get('series') or ''}, open('%s/%s_meta.json' % (OUT, item['id']), 'w'))
    if item['kind'] == 'hook':
        img.save('%s/%s_hook.jpg' % (OUT, item['id']), quality=90); return
    make_cover(title, item.get('series'), w, h, '%s/%s_%s.jpg' % (OUT, item['id'], item['kind']), bg=bgp)

feed = json.loads(os.environ['TEST_ITEMS']) if os.environ.get('TEST_ITEMS') else json.load(urllib.request.urlopen(FEED, timeout=180))
print('items:', [(i['id'], i['kind'], i.get('use_person')) for i in feed.get('items', [])])
for it in feed.get('items', []):
    if os.path.exists('%s/%s_%s.jpg' % (OUT, it['id'], it['kind'])) and os.path.exists('%s/%s_%s_bg.jpg' % (OUT, it['id'], it['kind'])): print('exists', it['id']); continue
    p = it['prompt'] + ' Photorealistic, natural light, no text, no logos, no watermark.'
    src = None
    p += ' No faces, no portraits, no identifiable people; hands or silhouettes from behind only.'
    for name, fn in [('klein', lambda: gen_klein(p, False, it['w'], it['h'])), ('zimage', lambda: gen_zimage(p, it['w'], it['h']))]:
        try:
            src = fn(); print('generated', it['kind'], 'with', name, flush=True); break
        except Exception as e:
            print('fail', name, repr(e)[:300], flush=True)
    if src:
        try: compose(src, it)
        except Exception as e: print('compose fail', repr(e)[:300])
files = sorted(glob.glob(OUT + '/*.jpg') + glob.glob(OUT + '/*.json'), key=os.path.getmtime)
for f in files[:-90]: os.remove(f)
print('done')
