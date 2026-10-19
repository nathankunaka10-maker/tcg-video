import os, shutil
from gradio_client import Client, handle_file
tok = os.environ.get('HF_TOKEN') or None
os.makedirs('probe_out', exist_ok=True)
PHOTO = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
def mk(s):
    try: return Client(s, token=tok)
    except TypeError: return Client(s, hf_token=tok)
def save(r, name):
    p = r[0] if isinstance(r, (list, tuple)) else r
    if isinstance(p, dict): p = p.get('path') or p.get('image') or p.get('url')
    if isinstance(p, (list, tuple)): p = p[0]
    if isinstance(p, dict): p = p.get('image') or p.get('path')
    if isinstance(p, dict): p = p.get('path')
    shutil.copy(p, 'probe_out/' + name); print('OK', name, flush=True)
tests = [
 ('z_image.png', 'Tongyi-MAI/Z-Image-Turbo', lambda c: c.predict(prompt='Photorealistic vertical photo: a smartphone lying on a wooden desk next to a laptop and coffee mug, the phone screen shows a new property enquiry notification, warm evening window light, shallow depth of field, real estate office', resolution='864x1152 ( 3:4 )', api_name='/generate')),
 ('qwen_edit_nathan.png', 'hugging-apps/qwen-qwen-image-2-1-turbo', lambda c: c.predict(prompt='The same young man from the photo, same face and grey hoodie, sitting at a desk in a modern office looking at his phone with a small smile, natural daylight, photorealistic, vertical', input_images=[{'image': handle_file(PHOTO), 'caption': None}], seed=7, resolution='1024', aspect_ratio='3:4', api_name='/generate')),
 ('klein_edit_nathan.png', 'black-forest-labs/flux-3-image-klein', lambda c: c.predict(prompt='The same young man from the reference photo, same face and grey hoodie, standing outside a modern house holding keys and smiling slightly, golden hour, photorealistic, vertical', input_images=[{'image': handle_file(PHOTO), 'caption': None}], width=864, height=1152, api_name='/generate')),
]
for name, sp, fn in tests:
    try:
        r = fn(mk(sp)); print('RAW', name, str(r)[:300], flush=True); save(r, name)
    except Exception as e:
        print('FAIL', name, repr(e)[:400], flush=True)
