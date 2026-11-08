"""Faceless character clip bank (8 Nov 2026, Nathan approved option 2).
One consistent, anonymous character for story reels: Nathan's build and grey hoodie (from his reference photo for consistency),
but the face is NEVER shown: from behind, over the shoulder, hands only, or a silhouette against a screen or window.
Step 1: a still per shot (FLUX Klein, free HF Space). Step 2: a face check (OpenCV) rejects any still where a face is visible.
Step 3: animate the still (Wan 2.2 image-to-video, free HF Space). Stops cleanly when the free daily GPU quota runs out."""
import os, json, random, shutil, subprocess, datetime, urllib.request
from gradio_client import Client, handle_file

PHOTO = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/nathan_ref.jpg'
BASE = 'https://raw.githubusercontent.com/nathankunaka10-maker/tcg-video/main/assets/faceless/'
OUT = 'assets/faceless'
MAX_NEW = int(os.environ.get('MAX_NEW', '4'))
KEEP = 30
LOOK = (' Same young man as in the reference photo: same build, same short dark hair, plain grey hoodie. '
        'His face is NOT visible at all. Cinematic, moody, soft cool monitor light, dark modern home office, shallow depth of field, '
        'realistic photo, vertical 9:16 frame, no text, no logos, no watermark.')
SHOTS = [
 ('desk_back', 'Shot from directly behind him: he sits at a desk facing two glowing monitors full of dashboards, back of his head and shoulders only.'),
 ('hands_keys', 'Close-up of his hands typing on a laptop keyboard, hoodie sleeves visible, screen glow on the hands, face out of frame.'),
 ('window_sil', 'He stands as a dark silhouette in front of a large window at night with city lights, seen from behind, phone in one hand.'),
 ('shoulder_phone', 'Over-the-shoulder shot from behind: he holds a phone showing a new message notification, only the back of his head and shoulder visible.'),
 ('hood_up_back', 'From behind, hood up, he leans toward a monitor with code and charts at night, face completely hidden by the hood.'),
 ('hands_notebook', 'Top-down close-up of his hands writing a plan in a notebook next to a laptop and a coffee mug, face not in frame.'),
 ('walk_away', 'He walks away from the camera down a dim hallway toward a lit room, seen from behind, hood down.'),
 ('chair_turn', 'Low angle from behind his office chair: he leans back with hands behind his head looking at screens full of messages.'),
]
MOTION = {
 'desk_back': 'He types and glances between the two screens, subtle head movement, camera stays behind him.',
 'hands_keys': 'Fast natural typing, screen light flickers slightly.',
 'window_sil': 'He lifts the phone and looks at it, city lights twinkle, he stays a silhouette.',
 'shoulder_phone': 'His thumb taps the notification and scrolls, the camera stays over the shoulder.',
 'hood_up_back': 'He leans closer to the screen and types, the hood keeps his face hidden.',
 'hands_notebook': 'He writes a short line and underlines it, steam rises from the mug.',
 'walk_away': 'He walks slowly away from the camera, steady handheld movement.',
 'chair_turn': 'He leans back slowly and the screens update with new messages.',
}
tok = os.environ.get('HF_TOKEN') or None

def client(space):
    try: return Client(space, token=tok)
    except TypeError: return Client(space, hf_token=tok)

def first_path(r):
    p = r[0] if isinstance(r, (list, tuple)) else r
    for _ in range(4):
        if isinstance(p, (list, tuple)): p = p[0]
        elif isinstance(p, dict): p = p.get('image') or p.get('video') or p.get('path') or p.get('url')
        else: break
    return p

def face_visible(path):
    """True when OpenCV finds a frontal or profile face: such stills are thrown away (the character stays faceless)."""
    import cv2
    img = cv2.imread(path)
    if img is None: return True
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for xml in ['haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml']:
        cc = cv2.CascadeClassifier(cv2.data.haarcascades + xml)
        if len(cc.detectMultiScale(g, 1.1, 6, minSize=(60, 60))):
            return True
    return False

try:
    manifest = json.load(urllib.request.urlopen(BASE + 'manifest.json', timeout=30))
except Exception:
    manifest = []
os.makedirs(OUT, exist_ok=True)
have = {m.split('__')[0] for m in manifest}
shots = sorted(SHOTS, key=lambda s: (s[0] in have, random.random()))  # shots we do not have yet go first
today = datetime.datetime.utcnow().strftime('%Y%m%d')
klein = client('black-forest-labs/flux-3-image-klein')
wan = client('zerogpu-aoti/wan2-2-fp8da-aoti-faster')
made = 0
for key, shot in shots:
    if made >= MAX_NEW: break
    try:
        still = None
        for attempt in range(2):
            r = klein.predict(prompt=shot + LOOK, input_images=[{'image': handle_file(PHOTO), 'caption': None}], width=720, height=1280, api_name='/generate')
            p = first_path(r)
            if p and not face_visible(p):
                still = p; break
            print('face visible or no image, retrying', key)
        if not still:
            continue
        r = wan.predict(input_image=handle_file(still), prompt=MOTION[key] + ' Realistic, subtle, the face is never shown.', duration_seconds=3.5, randomize_seed=True, api_name='/generate_video')
        src = first_path(r)
        name = '%s__%s.mp4' % (key, today)
        tmp = os.path.join(OUT, 'raw_' + name)
        shutil.copy(src, tmp)
        dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', tmp]).decode().strip())
        if dur < 2.0:
            os.remove(tmp); continue
        # face check on the middle and last frame of the clip too (motion can turn the head)
        bad = False
        for t in (dur / 2, dur - 0.7):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '%.2f' % t, '-i', tmp, '-frames:v', '1', 'chk.jpg'], check=True)
            if face_visible('chk.jpg'): bad = True
        if bad:
            print('face appeared in motion, dropped', key); os.remove(tmp); continue
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-t', '%.2f' % (dur - 0.5), '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-an', os.path.join(OUT, name)], check=True)
        os.remove(tmp)
        manifest.append(name); made += 1; print('ok', name, dur, flush=True)
    except Exception as e:
        print('stopped:', str(e)[:200])
        if 'exceed' in str(e).lower() or 'quota' in str(e).lower(): break
manifest = list(dict.fromkeys(m for m in manifest if os.path.exists(os.path.join(OUT, m)) or m.endswith('.mp4')))[-KEEP:]
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'))
for f in os.listdir(OUT):
    if f.endswith('.mp4') and f not in manifest:
        os.remove(os.path.join(OUT, f))
print('new faceless clips:', made, 'bank size:', len(manifest))
