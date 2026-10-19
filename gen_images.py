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
    w, h = item['w'], item['h']
    img = fill(Image.open(src).convert('RGB'), w, h)
    if item['kind'] == 'hook':
        img.save('%s/%s_hook.jpg' % (OUT, item['id']), quality=90); return
    text = (item.get('text') or '').strip()
    grad = Image.new('L', (1, h))
    for y in range(h):
        k = max(0, (y - h * 0.32) / (h * 0.68)); grad.putpixel((0, y), int(235 * min(1, k * 1.15)))
    shade = Image.new('RGB', (w, h), (6, 10, 20))
    img = Image.composite(shade, img, grad.resize((w, h)))
    d = ImageDraw.Draw(img)
    size = 96
    while size > 48:
        f = font(size); lines = textwrap.wrap(text, width=max(8, int(w / (size * 0.56))))
        lh = int(size * 1.08); block = lh * len(lines)
        if len(lines) <= 5 and all(d.textlength(l, font=f) < w - 140 for l in lines): break
        size -= 6
    y = h - 170 - block
    d.rectangle((70, y - 44, 190, y - 30), fill=(34, 211, 238))
    for l in lines:
        d.text((72, y + 4), l, font=f, fill=(0, 0, 0))
        d.text((70, y), l, font=f, fill=(255, 255, 255)); y += lh
    fb = font(34)
    d.text((70, h - 100), 'the', font=fb, fill=(156, 163, 175))
    d.text((70 + d.textlength('the', font=fb), h - 100), 'copygrind3r', font=fb, fill=(6, 182, 212))
    img.save('%s/%s_%s.jpg' % (OUT, item['id'], item['kind']), quality=90)

feed = json.loads(os.environ['TEST_ITEMS']) if os.environ.get('TEST_ITEMS') else json.load(urllib.request.urlopen(FEED, timeout=180))
print('items:', [(i['id'], i['kind'], i.get('use_person')) for i in feed.get('items', [])])
for it in feed.get('items', []):
    if os.path.exists('%s/%s_%s.jpg' % (OUT, it['id'], it['kind'])): print('exists', it['id']); continue
    p = it['prompt'] + ' Photorealistic, natural light, no text, no logos, no watermark.'
    src = None
    for name, fn in [('klein', lambda: gen_klein(p, it.get('use_person'), it['w'], it['h'])), ('zimage', lambda: gen_zimage(p.replace('the same young man from the reference photo, same face and grey hoodie', 'a young man in a grey hoodie'), it['w'], it['h']))]:
        try:
            src = fn(); print('generated', it['kind'], 'with', name, flush=True); break
        except Exception as e:
            print('fail', name, repr(e)[:300], flush=True)
    if src:
        try: compose(src, it)
        except Exception as e: print('compose fail', repr(e)[:300])
files = sorted(glob.glob(OUT + '/*.jpg'), key=os.path.getmtime)
for f in files[:-45]: os.remove(f)
print('done')
