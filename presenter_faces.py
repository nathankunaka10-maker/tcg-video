"""Generate invented presenter candidates (never a real person, never Nathan) with free HF ZeroGPU image spaces.
Writes assets/presenter/presenter_<KEY>.png. Skips keys that already exist, so reruns only fill gaps."""
import os, sys, shutil, time
from gradio_client import Client

tok = os.environ.get('HF_TOKEN') or None
OUT = os.path.join('assets', 'presenter')
os.makedirs(OUT, exist_ok=True)

BASE = (" Vertical smartphone front-camera selfie video still, 9:16, shot on an iPhone held at arm's length at eye level. "
        "{p} looks straight into the lens mid-sentence with a relaxed, friendly, natural expression, lips slightly parted. "
        "{p} holds a small black wireless clip-on microphone transmitter (matchbox sized, like a DJI Mic) between thumb and fingers just below the chin. "
        "Indoors, soft window daylight from one side, an ordinary lived-in apartment softly out of focus behind. "
        "Real unretouched skin with visible pores and small blemishes, a few flyaway hairs, slight phone sensor noise, mild compression, "
        "slightly imperfect off-centre framing, head, shoulders and upper chest in frame, the hand with the mic in the lower third. "
        "Candid amateur phone footage, not a model, not a studio, no glamour, no text, no watermark, no logo.")
PEOPLE = {
    'A': ("An ordinary 27 year old woman with shoulder length dark brown hair loosely tucked behind one ear, light olive skin, "
          "wearing a plain oatmeal crewneck sweater.", 'She'),
    'B': ("An ordinary 29 year old man with short slightly messy light brown hair and light stubble, fair skin, "
          "wearing a faded navy t-shirt under an open grey overshirt.", 'He'),
    'C': ("An ordinary 26 year old woman with curly black hair tied up in a loose bun, warm medium brown skin, "
          "wearing a simple olive green hoodie.", 'She'),
}

def client(space):
    try: return Client(space, token=tok, verbose=False)
    except TypeError: return Client(space, hf_token=tok, verbose=False)

def first_path(r):
    p = r[0] if isinstance(r, (list, tuple)) else r
    for _ in range(4):
        if isinstance(p, (list, tuple)): p = p[0]
        elif isinstance(p, dict): p = p.get('image') or p.get('path') or p.get('url')
        else: break
    return p

def zimage(prompt):
    return first_path(client('Tongyi-MAI/Z-Image-Turbo').predict(prompt=prompt, resolution='864x1536 ( 9:16 )', api_name='/generate'))

def klein(prompt):
    return first_path(client('black-forest-labs/flux-3-image-klein').predict(prompt=prompt, input_images=[], width=864, height=1536,
                                                                               prompt_upsampling=False, api_name='/generate'))

def qwen(prompt):
    return first_path(client('hugging-apps/qwen-qwen-image-2-1-turbo').predict(prompt=prompt, input_images=[], resolution='1536',
                                                                                aspect_ratio='9:16', api_name='/generate'))

keys = [k for k in (sys.argv[1:] or os.environ.get('FACES', 'A,B,C').split(',')) if k]
for k in keys:
    out = os.path.join(OUT, 'presenter_%s.png' % k)
    if os.path.exists(out) and not os.environ.get('FORCE'):
        print('exists', out); continue
    desc, p = PEOPLE[k]
    prompt = desc + BASE.format(p=p).replace('. ' + p.lower(), '. ' + p)
    for fn in (zimage, klein, qwen):
        try:
            src = fn(prompt)
            from PIL import Image
            Image.open(src).convert('RGB').save(out)
            print('ok', k, fn.__name__, flush=True)
            break
        except Exception as e:
            print('fail', k, fn.__name__, str(e)[:200], flush=True); time.sleep(3)
