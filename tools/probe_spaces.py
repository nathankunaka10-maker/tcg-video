"""Probe free HF Spaces: print API, then try one generation each. Outputs to probe_out/."""
import os, sys, json, shutil, traceback
from gradio_client import Client, handle_file
tok = os.environ.get('HF_TOKEN') or None
os.makedirs('probe_out', exist_ok=True)
SPACES = (os.environ.get('SPACES') or 'Tongyi-MAI/Z-Image-Turbo,black-forest-labs/flux-3-image-klein,hugging-apps/qwen-qwen-image-2-1-turbo,black-forest-labs/FLUX.1-Kontext-Dev,black-forest-labs/FLUX.2-dev').split(',')
PHOTO = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
def mk(space):
    try: return Client(space, token=tok)
    except TypeError: return Client(space, hf_token=tok)
for sp in SPACES:
    print('=' * 20, sp, flush=True)
    try:
        c = mk(sp)
        api = c.view_api(print_info=False, return_format='dict')
        eps = api.get('named_endpoints', {})
        for name, info in eps.items():
            ps = [(p.get('parameter_name'), p.get('python_type', {}).get('type'), p.get('parameter_default')) for p in info.get('parameters', [])]
            print('  EP', name, ps, flush=True)
        json.dump(api, open('probe_out/%s.api.json' % sp.replace('/', '__'), 'w'), default=str)
    except Exception as e:
        print('  CLIENT FAIL', repr(e)[:300], flush=True)
