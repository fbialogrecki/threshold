from pathlib import Path

import pytest
from media.images import InvalidImageError, process_image
from PIL import Image


def test_process_image_rejects_more_than_sixteen_million_pixels(tmp_path: Path) -> None:
    path = tmp_path / "large.png"
    Image.new("1", (5_000, 4_000)).save(path, format="PNG")

    with pytest.raises(InvalidImageError, match="image dimensions are too large"):
        process_image(path, "image/png", "post_image")


def test_process_image_resizes_before_rgb_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "large.png"
    Image.new("RGBA", (2_000, 1_000), color=(20, 40, 60, 255)).save(path, format="PNG")
    converted_sizes: list[tuple[int, int]] = []
    original_convert = Image.Image.convert

    def record_convert(image: Image.Image, *args: object, **kwargs: object) -> Image.Image:
        mode = args[0] if args else kwargs.get("mode")
        if mode == "RGB":
            converted_sizes.append(image.size)
        return original_convert(image, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Image.Image, "convert", record_convert)

    processed = process_image(path, "image/png", "post_image")

    assert set(processed.derivatives) == {"post_1280", "post_480"}
    assert converted_sizes
    assert (2_000, 1_000) not in converted_sizes
    assert max(width * height for width, height in converted_sizes) <= 1280 * 1280
