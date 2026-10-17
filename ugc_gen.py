"""Grow the AI clip bank of Nathan (free Wan 2.2 Space on Hugging Face, ZeroGPU quota).
Desk-only, everyday actions. No invented events, no talking. Stops cleanly when the daily quota is used."""
import os, json, random, shutil, subprocess, datetime, urllib.request
from gradio_client import Client, handle_file

PHOTO = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
BASE = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/ugc/'
OUT = 'assets/ugc'
MAX_NEW = int(os.environ.get('MAX_NEW', '5'))
KEEP = 40
STYLE = ' Natural handheld phone footage, soft daylight, realistic subtle movement, no text on screen.'
PROMPTS = [
 'A young man in a grey hoodie sits at a desk and types on a laptop, focused, glancing at the screen.',
 'A young man in a grey hoodie picks up his phone, reads a message, and gives a small satisfied smile.',
 'A young man in a grey hoodie leans back in his chair, thinks for a moment, then leans forward and nods.',
 'A young man in a grey hoodie looks at a laptop screen, raises his eyebrows slightly, then looks into the camera.',
 'A young man in a grey hoodie writes something in a notebook on the desk, then looks up.',
 'A young man in a grey hoodie takes a sip from a mug, sets it down, and turns back to the laptop.',
 'A young man in a grey hoodie rubs his chin while reading something on a laptop, then nods slowly.',
 'A young man in a grey hoodie scrolls on his phone, pauses, and looks up at the camera with a small shrug.',
 'A young man in a grey hoodie closes his laptop halfway, looks at the camera and gives a confident nod.',
 'A young man in a grey hoodie stretches his arms behind his head and smiles briefly at the camera.',
]
tok = os.environ.get('HF_TOKEN') or None
try:
    c = Client('zerogpu-aoti/wan2-2-fp8da-aoti-faster', token=tok)
except TypeError:
    c = Client('zerogpu-aoti/wan2-2-fp8da-aoti-faster', hf_token=tok)

try:
    manifest = json.load(urllib.request.urlopen(BASE + 'manifest.json', timeout=30))
except Exception:
    manifest = ['clip1.mp4', 'bank_typing.mp4', 'bank_phone.mp4']
os.makedirs(OUT, exist_ok=True)
today = datetime.datetime.utcnow().strftime('%Y%m%d')
prompts = PROMPTS[:]; random.shuffle(prompts)
made = 0
for i, p in enumerate(prompts[:MAX_NEW]):
    try:
        r = c.predict(input_image=handle_file(PHOTO), prompt=p + STYLE, duration_seconds=3.5,
                      randomize_seed=True, api_name='/generate_video')
        src = r[0]['video'] if isinstance(r[0], dict) else r[0]
        name = 'ugc_%s_%d.mp4' % (today, i)
        shutil.copy(src, os.path.join(OUT, name))
        dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(OUT, name)]).decode().strip())
        if dur < 2.0:
            os.remove(os.path.join(OUT, name)); continue
        manifest.append(name); made += 1; print('ok', name, dur, flush=True)
    except Exception as e:
        print('stopped:', str(e)[:200]); 
        if 'exceed' in str(e).lower() or 'quota' in str(e).lower(): break
manifest = list(dict.fromkeys(manifest))
seeds = [m for m in manifest if not m.startswith('ugc_')]
rest = [m for m in manifest if m.startswith('ugc_')][-(KEEP - len(seeds)):]
json.dump(seeds + rest, open(os.path.join(OUT, 'manifest.json'), 'w'))
for f in os.listdir(OUT):
    if f.startswith('ugc_') and f not in rest:
        os.remove(os.path.join(OUT, f))
print('new clips:', made, 'bank size:', len(seeds + rest))
