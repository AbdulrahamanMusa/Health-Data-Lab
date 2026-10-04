"""Image preparation and the bundled sample library.

Every image is decoded and re-encoded before it goes anywhere: this strips
EXIF and other embedded metadata (which can carry device, date, location or
patient labels), fixes orientation, and resizes to a size vision models read
well.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
MAX_EDGE = 1568  # long edge sent to the models
THUMB_EDGE = 360
MAX_UPLOAD_MB = 12
MIN_EDGE = 200


@dataclass(frozen=True)
class Prepared:
    jpeg: bytes
    width: int
    height: int
    digest: str  # SHA-256 of the prepared image: a stable case ID

    def data_url(self) -> str:
        return "data:image/jpeg;base64," + base64.b64encode(self.jpeg).decode()


class ImageError(ValueError):
    pass


def prepare(raw: bytes, max_edge: int = MAX_EDGE) -> Prepared:
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageError(f"The image is larger than {MAX_UPLOAD_MB} MB.")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ImageError("This file is not an image the app can read (use JPG, PNG, TIFF or WebP).") from e
    im = ImageOps.exif_transpose(im).convert("RGB")
    if min(im.size) < MIN_EDGE:
        raise ImageError(f"The image is too small ({im.width}×{im.height}). Use at least {MIN_EDGE} px on each side.")
    im.thumbnail((max_edge, max_edge), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=90, optimize=True)  # no exif= argument: metadata is dropped
    data = out.getvalue()
    return Prepared(jpeg=data, width=im.width, height=im.height, digest=hashlib.sha256(data).hexdigest())


def thumbnail_url(raw: bytes) -> str:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


@cache
def samples() -> list[dict]:
    meta = json.loads((SAMPLES_DIR / "samples.json").read_text(encoding="utf-8"))
    for s in meta:
        s["thumb"] = thumbnail_url((SAMPLES_DIR / s["file"]).read_bytes())
    return meta


@cache
def sample_image(sample_id: str) -> Prepared:
    s = next(x for x in samples() if x["id"] == sample_id)
    return prepare((SAMPLES_DIR / s["file"]).read_bytes())
