"""Branded post covers: one fixed frame for every post so the profile grid reads like a wallpaper
(same idea as Fabrizio Romano's fixed template). Faceless background photo, series chip, short
uppercase title with one cyan keyword, wordmark. All text sits inside the centre 3:4 area that
Instagram's profile grid shows, so nothing gets cropped."""
import os, glob, re, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

CYAN = (34, 211, 238)
INK = (6, 10, 20)
KEYWORDS = re.compile(r'(enquir|lead|repl|viewing|night|midnight|weekend|mobile|form|inbox|call|book|minute|hour|second|cold|leak|missed|lost|slow|fast|free|audit|agent|tenant|buyer)', re.I)

def font(size, weight='Black'):
    for f in ['/usr/share/fonts/opentype/inter/Inter-%s.otf' % weight, '/usr/share/fonts/truetype/inter/Inter-%s.ttf' % weight,
              '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if os.path.exists(f): return ImageFont.truetype(f, size)
    hits = glob.glob('/usr/share/fonts/**/Inter*%s*' % weight, recursive=True)
    return ImageFont.truetype(hits[0], size) if hits else ImageFont.load_default()

def short_title(text, max_words=7):
    """Fallback when no cover_title was written: first clause, max 7 words, no trailing filler."""
    t = re.sub(r'#\w+', '', str(text or '')).strip()
    t = re.split(r'(?<=[.!?:])\s|\s[—–-]\s|,\s', t)[0].strip(' .,:;!?')
    w = t.split()
    if len(w) > max_words:
        w = w[:max_words]
        while w and w[-1].lower() in {'to', 'the', 'a', 'an', 'and', 'or', 'of', 'for', 'on', 'in', 'your', 'with', 'at', 'get', 'is'}:
            w.pop()
    return ' '.join(w)

def fill(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s + 1), int(img.height * s + 1)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))

def background(bg, w, h):
    if bg and os.path.exists(bg):
        try:
            img = fill(Image.open(bg).convert('RGB'), w, h)
            img = ImageEnhance.Color(img).enhance(0.85)
            img = ImageEnhance.Brightness(img).enhance(0.62)
            return img
        except Exception as e:
            print('cover bg failed:', e)
    img = Image.new('RGB', (w, h), INK)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 54): d.line([(x, 0), (x, h)], fill=(14, 22, 38), width=1)
    for y in range(0, h, 54): d.line([(0, y), (w, y)], fill=(14, 22, 38), width=1)
    glow = Image.new('RGB', (w, h), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse((w * 0.2, h * 0.25, w * 0.8, h * 0.75), fill=(10, 60, 80))
    return Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), 0.5)

def make_cover(title, series, w, h, out, bg=None, number=None):
    img = background(bg, w, h)
    # safe area = the centre 3:4 crop the profile grid shows
    sh = min(h, int(w * 4 / 3)); top = (h - sh) // 2
    sw = min(w, int(h * 3 / 4)); left = (w - sw) // 2
    M = 64
    # darken bottom 60% of the safe area for the headline
    grad = Image.new('L', (1, h))
    for y in range(h):
        k = (y - (top + sh * 0.30)) / (sh * 0.55)
        grad.putpixel((0, y), int(225 * max(0, min(1, k))))
    img = Image.composite(Image.new('RGB', (w, h), INK), img, grad.resize((w, h)))
    d = ImageDraw.Draw(img)
    # series chip, top left of the safe area
    fc = font(34, 'Black'); lab = (series or 'AGENT PLAYBOOK').upper()
    tw = d.textlength(lab, font=fc)
    x0, y0 = left + M, top + M
    d.rounded_rectangle((x0, y0, x0 + tw + 44, y0 + 64), radius=14, fill=CYAN)
    d.text((x0 + 22, y0 + 12), lab, font=fc, fill=INK)
    if number:
        fn = font(30, 'Bold'); s = '#%03d' % int(number)
        d.text((left + sw - M - d.textlength(s, font=fn), y0 + 16), s, font=fn, fill=(200, 210, 220))
    # title: uppercase, as big as fits in max 4 lines
    words = str(title or '').upper().split()
    if not words: words = ['ANSWER', 'EVERY', 'ENQUIRY']
    hi = None
    for i in range(len(words) - 1, -1, -1):
        if KEYWORDS.search(words[i]): hi = i; break
    if hi is None: hi = len(words) - 1
    maxw = sw - 2 * M
    size = 150
    while size > 54:
        f = font(size, 'Black'); lines = []; cur = []
        for i, wd in enumerate(words):
            test = ' '.join(x for _, x in cur + [(i, wd)])
            if cur and d.textlength(test, font=f) > maxw:
                lines.append(cur); cur = [(i, wd)]
            else:
                cur.append((i, wd))
        if cur: lines.append(cur)
        if len(lines) <= 4 and all(d.textlength(' '.join(x for _, x in l), font=f) <= maxw for l in lines): break
        size -= 6
    lh = int(size * 1.02)
    block = lh * len(lines)
    y = top + sh - 200 - block
    d.rectangle((left + M, y - 40, left + M + 110, y - 28), fill=CYAN)
    for line in lines:
        x = left + M
        for i, wd in line:
            col = CYAN if i == hi else (255, 255, 255)
            d.text((x + 3, y + 4), wd, font=f, fill=(0, 0, 0))
            d.text((x, y), wd, font=f, fill=col)
            x += d.textlength(wd + ' ', font=f)
        y += lh
    # wordmark
    fb = font(36, 'Bold')
    yb = top + sh - M - 44
    d.text((left + M, yb), 'the', font=fb, fill=(170, 178, 190))
    d.text((left + M + d.textlength('the', font=fb), yb), 'copygrind3r', font=fb, fill=CYAN)
    img.save(out, quality=92)
    return out

if __name__ == '__main__':
    import sys
    make_cover(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else None)
