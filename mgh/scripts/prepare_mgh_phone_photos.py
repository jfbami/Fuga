import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/photo_decode_packages'))
import pillow_heif
from PIL import Image, ImageOps, ExifTags

pillow_heif.register_heif_opener()
DEST = ROOT / 'outputs/MGH_Project/capture/independent_phone_20261017'
DEST.mkdir(exist_ok=False)
(DEST / 'originals').mkdir()
(DEST / 'normalized').mkdir()
photos = []
for filename, room in [('IMG_5385.HEIC', '430 Computer Classroom'), ('IMG_5386.HEIC', '440')]:
    source = Path('C:/Users/jfbaa/Downloads') / filename
    original = DEST / 'originals' / filename
    shutil.copy2(source, original)
    assert original.read_bytes() == source.read_bytes()
    with Image.open(original) as im:
        exif = im.getexif()
        values = dict(exif)
        try:
            values.update(exif.get_ifd(34665))
        except (KeyError, ValueError):
            pass
        keep = {271, 272, 274, 305, 306, 33434, 33437, 34855, 36867, 37386, 40962, 40963, 41989, 42036}
        camera = {ExifTags.TAGS.get(k, str(k)): str(v) for k, v in values.items() if k in keep}
        normalized = ImageOps.exif_transpose(im).convert('RGB')
        output = DEST / 'normalized' / (source.stem + '.png')
        normalized.save(output)
        preview = normalized.copy()
        preview.thumbnail((1200, 1200))
        preview.save(ROOT / 'work' / (source.stem + '_preview.jpg'), quality=95)
        photos.append(dict(original_filename=filename, sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
            byte_count=original.stat().st_size, source=str(source), user_location=f'in front of {room}',
            room_identity_source='user message', independently_surveyed_camera_position=None,
            independently_known_facing_direction=None, camera_metadata=camera,
            normalized_image=f'normalized/{output.name}', normalized_width=normalized.width,
            normalized_height=normalized.height, normalized_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            camera_calibration_verified=False, mapping_reference=False))
manifest = dict(received_utc=datetime.now(timezone.utc).isoformat(), photos=photos,
    protocol=dict(role='Independent-phone diagnostic queries; never mapping references',
        primary_baseline='Unchanged v3 localizer with no query calibration: appearance retrieval only; no pose acceptance is claimed.',
        optional_geometry='EXIF-derived calibration estimates, if available, are exploratory and must not be reported as metric validation.',
        allowed_comparison='Audit-motivated mutual-nearest-neighbour retrieval vs unchanged retrieval. Fixed design before matching these photos; retain unchanged geometric thresholds.',
        later_tuning='These two images become development diagnostics once inspected; later variants require new held-out photos.',
        user_room_labels_used_by_solver=False, surveyed_accuracy_claim=False))
(DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
