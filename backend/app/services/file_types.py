"""Classify uploaded PDFs, scanned images, and photos."""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageSequence, UnidentifiedImageError

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS

ACCEPT_LABEL = "PDF, scanned images, and photos (PNG, JPG, TIFF, BMP, WebP, GIF)"


def is_pdf_bytes(content: bytes) -> bool:
    return b"%PDF-" in (content[:1024] if content else b"")


def detect_image_kind(header: bytes) -> Optional[str]:
    if header.startswith(b"\x89PNG"):
        return "PNG image"
    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG photo"
    if header.startswith(b"GIF8"):
        return "GIF image"
    if header.startswith(b"BM"):
        return "BMP image"
    if header.startswith(b"RIFF") and b"WEBP" in header[:16]:
        return "WebP image"
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return "TIFF scan"
    return None


def detect_unsupported_kind(header: bytes) -> Optional[str]:
    if header.startswith(b"PK"):
        return "ZIP archive or Office document"
    stripped = header.lstrip()
    if stripped.startswith(b"<!DOCTYPE") or stripped.lower().startswith(b"<html"):
        return "HTML document"
    try:
        sample = header[:80].decode("utf-8")
        if sample and all(ch.isprintable() or ch.isspace() for ch in sample):
            return "plain text"
    except UnicodeDecodeError:
        pass
    return None


def classify_bytes(content: bytes, filename: str) -> str:
    """Return 'pdf' or 'image'. Raise ValueError for unsupported files."""
    if not content:
        raise ValueError(f"The file '{filename}' is empty.")

    suffix = Path(filename).suffix.lower()
    if is_pdf_bytes(content) or suffix in PDF_EXTENSIONS:
        if is_pdf_bytes(content):
            return "pdf"

    kind = detect_image_kind(content[:64])
    if kind or suffix in IMAGE_EXTENSIONS:
        try:
            from io import BytesIO

            with Image.open(BytesIO(content[: min(len(content), 64 * 1024)])):
                pass
        except (UnidentifiedImageError, OSError):
            if kind or suffix in IMAGE_EXTENSIONS:
                return "image"
            raise ValueError(
                f"'{filename}' looks like an image but could not be opened. "
                f"Please upload a {ACCEPT_LABEL}."
            )
        return "image"

    unsupported = detect_unsupported_kind(content[:64])
    if unsupported:
        raise ValueError(
            f"'{filename}' is a {unsupported}, not a supported document. "
            f"Please upload a {ACCEPT_LABEL}."
        )
    raise ValueError(
        f"'{filename}' is not a supported file. Please upload a {ACCEPT_LABEL}."
    )


def classify_path(file_path: str, filename: Optional[str] = None) -> str:
    name = filename or Path(file_path).name
    with open(file_path, "rb") as handle:
        header = handle.read(1024)
    return classify_bytes(header, name)


def count_image_frames(file_path: str) -> int:
    with Image.open(file_path) as img:
        frames = list(ImageSequence.Iterator(img))
        return max(len(frames), 1)


def rasterize_image_file(file_path: str, job_dir: Path) -> list:
    """Convert a photo/scan (including multi-page TIFF) into PNG page files."""
    job_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with Image.open(file_path) as img:
        frames = list(ImageSequence.Iterator(img))
        if not frames:
            frames = [img]
        for index, frame in enumerate(frames, start=1):
            converted = frame.convert("RGB")
            output_path = job_dir / f"page_{index}.png"
            converted.save(output_path, "PNG")
            paths.append(str(output_path))
    return paths


def is_supported_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS
