import asyncio, subprocess, os, json, shutil, base64, urllib.request
from playwright.async_api import async_playwright
FEED = 'https://natenathan.duckdns.org/webhook/video-content'
FPS = 30
req = urllib.request.Request(FEED, headers={'User-Agent': 'tcg-video'})
d = json.load(urllib.request.urlopen(req, timeout=180))
if d.get('skip'):
    print('nothing to render today'); raise SystemExit(0)
os.makedirs('out', exist_ok=True)
aud = None; adur = 0
if d.get('audio_b64'):
    open('narr.pcm', 'wb').write(base64.b64decode(d['audio_b64']))
    subprocess.run(['ffmpeg', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'narr.pcm', 'narr.wav'], check=True, capture_output=True)
    adur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', 'narr.wav']).decode().strip())
    aud = 'narr.wav'
segs = [d['hook']] + d['points'] + [d['statsLine'], d['cta']]
words = [max(len(s.split()), 3) for s in segs]
T = max(adur + 1.0, 18.0)
durs = [T * w / sum(words) for w in words]
async def main():
    shutil.rmtree('frames', ignore_errors=True); os.makedirs('frames')
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1080, 'height': 1920})
        await pg.goto('file://' + os.path.abspath('template.html'))
        await pg.evaluate('setData(%s)' % json.dumps({'d': d, 'durs': durs, 'T': T}))
        await pg.wait_for_timeout(400)
        for i in range(int(FPS * T)):
            await pg.evaluate('setT(%f)' % (i / FPS))
            await pg.screenshot(path='frames/f%04d.jpg' % i, type='jpeg', quality=88)
        await b.close()
asyncio.run(main())
cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i', 'frames/f%04d.jpg']
if aud: cmd += ['-i', aud, '-c:a', 'aac', '-b:a', '160k', '-shortest']
cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', 'out/latest.mp4']
subprocess.run(cmd, check=True, capture_output=True)
json.dump({'date': d['date'], 'id': d['id'], 'caption': d['caption'], 'duration': T, 'narrated': bool(aud)}, open('out/meta.json', 'w'))
print('rendered', T)
