from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning


@dataclass(frozen=True)
class ProcessedImage:
    content_type: str
    width: int
    height: int
    derivatives: dict[str, bytes]


class InvalidImageError(ValueError):
    pass


_CONTENT_TYPES_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 8192
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _validate_dimensions(image: Image.Image) -> None:
    width, height = image.size
    if (
        width <= 0
        or height <= 0
        or width > MAX_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise InvalidImageError("image dimensions are too large")


def _center_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _webp_bytes(image: Image.Image, *, size: tuple[int, int] | None = None) -> bytes:
    output = BytesIO()
    frame = image.convert("RGB")
    if size is not None:
        frame.thumbnail(size, Image.Resampling.LANCZOS)
    frame.save(output, format="WEBP", quality=86, method=6)
    return output.getvalue()


def process_image(path: Path, declared_content_type: str, context: str) -> ProcessedImage:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            image = Image.open(path)
            _validate_dimensions(image)
            image.load()
    except (DecompressionBombError, DecompressionBombWarning) as exc:
        raise InvalidImageError("image dimensions are too large") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("invalid image bytes") from exc

    detected_content_type = _CONTENT_TYPES_BY_FORMAT.get(image.format or "")
    if detected_content_type is None:
        raise InvalidImageError("unsupported image format")
    if detected_content_type != declared_content_type:
        raise InvalidImageError("declared content type does not match image bytes")

    derivatives: dict[str, bytes] = {}
    if context in {"user_avatar", "page_avatar"}:
        square = _center_square(image)
        derivatives["avatar_512"] = _webp_bytes(square, size=(512, 512))
        derivatives["avatar_256"] = _webp_bytes(square, size=(256, 256))
    elif context in {"post_image", "event_poster"}:
        derivatives["post_1280"] = _webp_bytes(image, size=(1280, 1280))
        derivatives["post_480"] = _webp_bytes(image, size=(480, 480))

    return ProcessedImage(
        content_type=detected_content_type,
        width=image.width,
        height=image.height,
        derivatives=derivatives,
    )
