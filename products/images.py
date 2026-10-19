"""Turns an uploaded photo into web-ready WebP variants."""

import io
from dataclasses import dataclass, field
from typing import Dict

from PIL import Image, ImageOps, UnidentifiedImageError

# Widths cover phone cards (400), desktop cards / phone detail (800) and the
# desktop detail page and zoom (1600).
VARIANT_WIDTHS = (400, 800, 1600)
WEBP_QUALITY = 82
# Refuse decompression bombs: 40 megapixels is well above any phone camera.
MAX_PIXELS = 40_000_000


class ImageProcessingError(Exception):
    """The upload isn't a usable image; the message is safe to show to staff."""


@dataclass
class ProcessedImage:
    width: int
    height: int
    variants: Dict[int, bytes] = field(default_factory=dict)  # width -> WebP bytes


def process_image(data: bytes) -> ProcessedImage:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise ImageProcessingError("That file isn't an image we can read. Use a JPEG, PNG or WebP photo.") from e

    image = ImageOps.exif_transpose(image)  # respect phone camera rotation
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")

    largest = None
    variants = {}  # keyed by the variant's real width, which srcset needs
    for width in VARIANT_WIDTHS:
        target = min(width, image.width)  # never upscale
        resized = image if target == image.width else image.resize(
            (target, round(image.height * target / image.width)), Image.LANCZOS
        )
        buffer = io.BytesIO()
        resized.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
        variants[target] = buffer.getvalue()
        largest = resized
        if target < width:
            break  # the original is smaller than this size; bigger variants would be identical
    return ProcessedImage(width=largest.width, height=largest.height, variants=variants)
