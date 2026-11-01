# Records a short animated walkthrough (GIF + MP4) of each prospect's demo page.
# Slugs come from the n8n webhook demo-slugs (latest prototypes). Skips slugs already rendered.
import json, os, subprocess, urllib.request, glob
from playwright.sync_api import sync_playwright
OUT = 'demos'; os.makedirs(OUT, exist_ok=True)
slugs = os.environ.get('SLUGS', '').split()
if not slugs:
    try:
        slugs = json.loads(urllib.request.urlopen('https://natenathan.duckdns.org/webhook/demo-slugs', timeout=60).read()).get('slugs', [])
    except Exception as e:
        print('slug fetch failed', e); slugs = []
done = set(os.path.basename(p)[:-4] for p in glob.glob(OUT + '/*.gif'))
todo = [s for s in slugs if s and s not in done][:25]
print('todo', todo)
with sync_playwright() as p:
    b = p.chromium.launch()
    for slug in todo:
        d = f'frames_{slug}'; os.makedirs(d, exist_ok=True); n = 0
        pg = b.new_page(viewport={'width': 900, 'height': 640}, device_scale_factor=1)
        def snap(k=1):
            global n
            for _ in range(k):
                pg.screenshot(path=f'{d}/{n:04d}.png'); n += 1
        try:
            pg.goto(f'https://thecopygrind3r-demo.pages.dev/{slug}', wait_until='networkidle', timeout=60000)
            pg.wait_for_timeout(1500); snap(6)
            for tab in ['Inbox', 'Website assistant']:
                loc = pg.get_by_text(tab, exact=True)
                if loc.count():
                    loc.first.click(); pg.wait_for_timeout(900); snap(5)
                    for _ in range(4):
                        pg.mouse.wheel(0, 260); pg.wait_for_timeout(250); snap(2)
                    pg.mouse.wheel(0, -2000); pg.wait_for_timeout(300)
            btn = pg.get_by_text('Play it step by step')
            first = pg.locator('text=/Flow/').first
            if first.count():
                first.click(); pg.wait_for_timeout(600)
            if btn.count():
                btn.first.click()
                for _ in range(10):
                    pg.wait_for_timeout(450); snap(1)
            snap(4)
        except Exception as e:
            print(slug, 'error', e)
        pg.close()
        if n < 5: continue
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '4', '-i', f'{d}/%04d.png', '-vf', 'fps=4,scale=600:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer', f'{OUT}/{slug}.gif'], check=False)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '4', '-i', f'{d}/%04d.png', '-vf', 'scale=900:-2', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', '24', f'{OUT}/{slug}.mp4'], check=False)
        print(slug, 'frames', n, os.path.getsize(f'{OUT}/{slug}.gif') if os.path.exists(f'{OUT}/{slug}.gif') else 0)
    b.close()
