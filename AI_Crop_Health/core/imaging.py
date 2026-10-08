"""
Compress uploaded images before they are stored.

Phone cameras produce 2-5MB JPEGs. Stored raw they fill the disk, slow every
page that shows them and cost farmers mobile data to re-download. The largest
file already in media/ is 1.5MB for a single leaf photo.

The disease model resizes to 224x224 anyway, so a 4000px original carries no
useful extra information once it has been diagnosed. We keep a generous 1600px
so a human reviewer can still zoom in.
"""

import io
import logging
import os

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1600
JPEG_QUALITY = 82
# Below this, re-encoding usually makes the file bigger rather than smaller.
MIN_BYTES_TO_BOTHER = 150 * 1024


def flatten_to_rgb(image):
    """
    Convert any image to RGB, compositing transparency onto white.

    JPEG has no alpha channel. Converting an RGBA image straight to RGB leaves
    transparent pixels black, so a leaf photo with a transparent background
    would be stored on a black rectangle. Split out from compress_image so it
    can be tested without depending on how well a fixture happens to compress.
    """
    if image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        converted = image.convert('RGBA')
        background.paste(converted, mask=converted.split()[-1])
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image


def compress_image(uploaded, max_dimension=MAX_DIMENSION, quality=JPEG_QUALITY):
    """
    Return a compressed copy of `uploaded`, or the original if not worth it.

    Never raises: if anything goes wrong the original file is returned
    unchanged, because losing a farmer's photo is far worse than storing a
    large one.
    """
    if not uploaded:
        return uploaded

    try:
        size = getattr(uploaded, 'size', 0) or 0
        if size and size < MIN_BYTES_TO_BOTHER:
            return uploaded

        uploaded.seek(0)
        image = Image.open(uploaded)

        # Phone photos carry EXIF orientation; without this a portrait photo is
        # stored sideways once the EXIF block is dropped on re-encode.
        image = ImageOps.exif_transpose(image)

        image = flatten_to_rgb(image)

        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        buffer = io.BytesIO()
        # Re-saving strips EXIF, which also removes GPS coordinates that phones
        # embed in photos - a privacy win we want, not a side effect to undo.
        image.save(buffer, format='JPEG', quality=quality, optimize=True, progressive=True)
        buffer.seek(0)

        if size and buffer.getbuffer().nbytes >= size:
            uploaded.seek(0)
            return uploaded

        base, _ = os.path.splitext(os.path.basename(uploaded.name))
        new_name = f'{base}.jpg'
        compressed = InMemoryUploadedFile(
            buffer, getattr(uploaded, 'field_name', None), new_name,
            'image/jpeg', buffer.getbuffer().nbytes, None,
        )
        logger.info(
            'Compressed upload %s: %d KB -> %d KB',
            uploaded.name, size // 1024, compressed.size // 1024,
        )
        return compressed

    except Exception:
        logger.exception('Image compression failed for %s; storing original',
                         getattr(uploaded, 'name', '<unknown>'))
        try:
            uploaded.seek(0)
        except Exception:
            pass
        return uploaded


def to_sanitised_bytes(uploaded, max_dimension=MAX_DIMENSION, quality=JPEG_QUALITY):
    """
    Return JPEG bytes of `uploaded` with every metadata block removed.

    Use this for anything that LEAVES this server. compress_image already drops
    EXIF, but it only ran on the copy written to our own database - the original
    file, GPS coordinates and all, was handed straight to the third-party
    diagnosis APIs. That is backwards: the farmer's exact field location was
    scrubbed from our storage and forwarded abroad.

    Re-encoding through PIL rebuilds the pixel data in a new container, so EXIF
    (including GPSInfo), XMP and IPTC blocks do not survive. Orientation is
    applied first so the image still appears the right way up once the EXIF
    orientation tag is gone.

    Falls back to the raw bytes if anything goes wrong: a diagnosis that still
    works beats one that fails closed, and the caller is already sending the
    image to a provider either way.
    """
    try:
        uploaded.seek(0)
    except (AttributeError, OSError):
        pass

    raw = uploaded.read()

    try:
        uploaded.seek(0)
    except (AttributeError, OSError):
        pass

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image = flatten_to_rgb(image)

        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        return buffer.getvalue()
    except Exception as exc:
        logger.warning(
            'Could not strip metadata from %s (%s); sending original bytes',
            getattr(uploaded, 'name', '<unnamed>'), exc,
        )
        return raw
