"""Bounded JPEG/PNG analysis. Source files are only opened for reading."""

import io
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import PIL
from PIL import Image, ImageStat

VERSION = f"dhash64-rgb-orientation-v2-pillow-{PIL.__version__}"
MAX_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 20_000_000
THUMB_SIZE = 256


class AnalysisCancelled(Exception):
    """Cooperative cancellation, distinct from an individual image failure."""


@dataclass
class ImageFeatures:
    thumbnail: bytes
    dhash: str
    red: int
    green: int
    blue: int
    width: int
    height: int
    low_detail: bool


def checkpoint(cancel):
    if cancel():
        raise AnalysisCancelled


def source_signature(path, root):
    """Reject links in every path component, including the root and its parents."""
    path = Path(os.path.abspath(path))
    root = Path(os.path.abspath(root))
    if path == root or not path.is_relative_to(root):
        raise OSError("Image is outside its saved library root")
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        attrs = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise OSError("Links and reparse points are not followed")
        if component == path and not stat.S_ISREG(info.st_mode):
            raise OSError("Image is not a regular file")
    return info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino


def analyze(path, root, size, modified_ns, orientation=1, cancel=lambda: False):
    checkpoint(cancel)
    before = source_signature(path, root)
    if before[:2] != (size, modified_ns):
        raise OSError("File changed since scanning; rescan first")
    if size > MAX_BYTES:
        raise ValueError("Image exceeds the 32 MiB input limit")
    # O_NOFOLLOW protects the final component where the platform provides it.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        identity = (opened.st_size, opened.st_mtime_ns, opened.st_dev, opened.st_ino)
        if identity != before or source_signature(path, root) != before:
            raise OSError("File or its path changed before decoding; rescan first")
        # Restrict decoders by actual content, not the filename extension.
        with Image.open(source, formats=("JPEG", "PNG")) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image exceeds the 20 million pixel limit")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated images are not supported in visual review")
            checkpoint(cancel)
            image.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            # Read only the orientation tag. Never traverse the GPS IFD or retain EXIF.
            orientation = image.getexif().get(0x0112, orientation)
            transforms = {
                2: Image.Transpose.FLIP_LEFT_RIGHT,
                3: Image.Transpose.ROTATE_180,
                4: Image.Transpose.FLIP_TOP_BOTTOM,
                5: Image.Transpose.TRANSPOSE,
                6: Image.Transpose.ROTATE_270,
                7: Image.Transpose.TRANSVERSE,
                8: Image.Transpose.ROTATE_90,
            }
            oriented = (
                image.transpose(transforms[orientation]) if orientation in transforms else image
            )
            rgba = oriented.convert("RGBA")
            clean = Image.new("RGB", rgba.size, "white")
            clean.paste(rgba, mask=rgba.getchannel("A"))
            grey = clean.convert("L")
            pixels = list(grey.resize((9, 8), Image.Resampling.LANCZOS).get_flattened_data())
            value = 0
            for row in range(8):
                for col in range(8):
                    value = (value << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
            means = [round(channel) for channel in ImageStat.Stat(clean).mean]
            output = io.BytesIO()
            clean.save(output, format="PNG")
            result = ImageFeatures(
                output.getvalue(),
                f"{value:016x}",
                *means,
                clean.width,
                clean.height,
                ImageStat.Stat(grey).stddev[0] < 3,
            )
        checkpoint(cancel)
        if source_signature(path, root) != before:
            raise OSError("File changed during decoding; rescan first")
        after = os.fstat(source.fileno())
        if (after.st_size, after.st_mtime_ns) != before[:2]:
            raise OSError("Opened file changed during decoding; rescan first")
    return result
