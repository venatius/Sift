import json
import os
import shutil
import subprocess
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional

import PIL
import pillow_heif
from PIL import Image, UnidentifiedImageError

pillow_heif.register_heif_opener()  # lets Pillow open HEIC/HEIF files

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
              ".tif", ".tiff", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp", ".mkv", ".avi", ".webm", ".mts"}
IMAGE_FORMATS = {"JPEG", "PNG", "GIF", "WEBP", "BMP", "TIFF", "HEIF"}
FFPROBE_TIMEOUT = 30  # seconds


class MetadataCancelled(Exception):
    """Raised when the user cancels while an extractor is running."""


@dataclass
class MetadataResult:
    status: str  # "ok", "unsupported", or "failed"
    media_kind: Optional[str] = None
    detected_format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    video_codec: Optional[str] = None
    capture_date: Optional[str] = None
    capture_date_source: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    orientation: Optional[int] = None
    error: Optional[str] = None
    retryable: bool = False


# ----- which extractor handles a file -----
def kind_for(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dng":
        return None
    detected = _kind_from_signature(path)
    if detected:
        return detected
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def _kind_from_signature(path):
    try:
        with open(path, "rb") as media_file:
            header = media_file.read(16)
    except OSError:
        return None
    if (header.startswith(b"\xff\xd8\xff") or header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith((b"GIF87a", b"GIF89a", b"BM"))
            or header.startswith((b"II*\x00", b"MM\x00*"))):
        return "image"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image"
    if header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"heic", b"heif", b"heix", b"hevc", b"hevx", b"mif1",
                     b"msf1", b"avif", b"avis"):
            return "image"
        return "video"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video"
    if header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return "video"
    if len(header) >= 1 and header[0] == 0x47:
        try:
            with open(path, "rb") as media_file:
                media_file.seek(188)
                if media_file.read(1) == b"\x47":
                    return "video"
        except OSError:
            pass
    return None


def ffprobe_path():
    return shutil.which("ffprobe")


@lru_cache(maxsize=1)
def _ffprobe_version():
    exe = ffprobe_path()
    if not exe:
        return "missing"
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True,
                             timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return out.stdout.split("\n")[0].split()[2]  # "ffprobe version X ..."
    except Exception:
        return "unknown"


def extractor_info(kind):
    """(name, version) used as the cache key for saved results."""
    if kind == "image":
        return "pillow", f"{PIL.__version__}+heif{pillow_heif.__version__}"
    if kind == "video":
        return "ffprobe", _ffprobe_version()
    return "none", "1"


def extract(path, kind, cancel_check):
    if kind == "image":
        return extract_image_metadata(path)
    if kind == "video":
        return extract_video_metadata(path, cancel_check)
    ext = os.path.splitext(path)[1].lower() or "no extension"
    return MetadataResult("unsupported", error=f"No extractor for '{ext}' files")


# ----- images -----
def _text(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = str(value).strip("\x00 ").strip()
    return value or None


def _capture_date(exif):
    try:
        exif_ifd = exif.get_ifd(0x8769)  # the "Exif" sub-block
    except Exception:
        exif_ifd = {}
    for tag, source in ((0x9003, "exif:DateTimeOriginal"),
                        (0x9004, "exif:DateTimeDigitized")):
        raw = _text(exif_ifd.get(tag))
        if raw:
            try:
                parsed = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                return parsed.isoformat(), source  # no timezone assumed
            except ValueError:
                continue
    return None, None


def extract_image_metadata(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(path) as probe:
                if probe.format == "HEIF":
                    probe.load()
                else:
                    probe.verify()
            with Image.open(path) as img:
                fmt = img.format
                if fmt not in IMAGE_FORMATS:
                    return MetadataResult("unsupported", detected_format=fmt,
                                          error=f"Actual format is {fmt}, not supported")
                width, height = img.size
                exif = img.getexif()
                orientation = exif.get(0x0112)
                capture, source = _capture_date(exif)
                return MetadataResult(
                    "ok", "image", fmt, width, height, None, None, capture, source,
                    _text(exif.get(0x010F)), _text(exif.get(0x0110)),
                    orientation if isinstance(orientation, int) else None,
                )
    except UnidentifiedImageError:
        return MetadataResult("failed", error="Not a readable image (corrupt or wrong format)")
    except Exception as e:
        return MetadataResult("failed", error=f"Could not read metadata: {e}",
                              retryable=isinstance(e, PermissionError))


# ----- videos -----
def _run_ffprobe(exe, path, cancel_check):
    cmd = [exe, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", "-i", path]  # a list: no shell, no quoting issues
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + FFPROBE_TIMEOUT
    while True:
        try:
            out, err = proc.communicate(timeout=0.2)
            return proc.returncode, out, err
        except subprocess.TimeoutExpired:
            if cancel_check():
                proc.kill()
                proc.communicate()
                raise MetadataCancelled
            if time.monotonic() > deadline:
                proc.kill()
                proc.communicate()
                raise TimeoutError(f"ffprobe took longer than {FFPROBE_TIMEOUT}s")


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_video_metadata(path, cancel_check):
    exe = ffprobe_path()
    if not exe:
        return MetadataResult("failed", error="ffprobe not found; install FFmpeg")
    try:
        code, out, err = _run_ffprobe(exe, path, cancel_check)
    except MetadataCancelled:
        raise
    except Exception as e:
        return MetadataResult("failed", error=f"ffprobe failed: {e}",
                              retryable=isinstance(e, (TimeoutError, PermissionError,
                                                       FileNotFoundError)))
    if code != 0:
        first = (err.decode("utf-8", "ignore").strip().splitlines() or ["unknown error"])[0]
        return MetadataResult("failed", error=f"Not a readable video: {first}")
    try:
        data = json.loads(out)
    except ValueError:
        return MetadataResult("failed", error="ffprobe returned unreadable output")

    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        return MetadataResult("failed", error="No video stream found")

    fmt = data.get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}

    # Prefer Apple's date (includes a UTC offset) over the generic creation_time.
    if tags.get("com.apple.quicktime.creationdate"):
        capture, source = tags["com.apple.quicktime.creationdate"], "quicktime:creationdate"
    elif tags.get("creation_time"):
        capture, source = tags["creation_time"], "container:creation_time"
    else:
        capture, source = None, None

    return MetadataResult(
        "ok", "video", fmt.get("format_name"),
        video.get("width"), video.get("height"),
        _float(fmt.get("duration")) or _float(video.get("duration")),
        video.get("codec_name"), capture, source,
        _text(tags.get("com.apple.quicktime.make")),
        _text(tags.get("com.apple.quicktime.model")), None,
    )
