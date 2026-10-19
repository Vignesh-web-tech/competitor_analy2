import io
import os
import re

import pytesseract
from PIL import Image

from cache import cache
from config import (
    MAX_IMAGE_BYTES,
    MAX_IMAGES_PER_PAGE,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
    OCR_ENABLED,
    OCR_LANG,
    TESSERACT_CMD,
)

DEFAULT_WINDOWS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _setup() -> bool:
    if not OCR_ENABLED:
        print("[ocr] OCR is disabled (OCR_ENABLED=false)")
        return False

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    elif os.path.exists(DEFAULT_WINDOWS_PATH):
        pytesseract.pytesseract.tesseract_cmd = DEFAULT_WINDOWS_PATH

    try:
        version = pytesseract.get_tesseract_version()
        print(f"[ocr] Tesseract {version} is ready")
        return True
    except Exception as exc:
        print(f"[ocr] Tesseract not available, OCR will be skipped: {exc}")
        return False


TESSERACT_AVAILABLE = _setup()


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 15:
        return ""
    readable = sum(1 for c in text if c.isalnum() or c.isspace())
    if readable / len(text) < 0.7:
        return ""  # mostly garbage characters
    return text


def ocr_image_bytes(data: bytes) -> str:
    """Run OCR on raw image bytes and return cleaned text ('' if nothing useful)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return ""

    if img.width < MIN_IMAGE_WIDTH or img.height < MIN_IMAGE_HEIGHT:
        return ""

    # Flatten transparency onto a white background, then convert to grayscale.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    img = img.convert("L")

    if max(img.size) > 3000:
        img.thumbnail((3000, 3000))

    try:
        raw = pytesseract.image_to_string(img, lang=OCR_LANG, timeout=30)
    except Exception as exc:
        print(f"[ocr] failed: {exc}")
        return ""
    return _clean(raw)


def ocr_images(context, image_urls: list) -> str:
    """Download images with the Playwright context, OCR them, and return the combined text."""
    if not TESSERACT_AVAILABLE or not image_urls:
        return ""

    results = []
    for url in image_urls[:MAX_IMAGES_PER_PAGE]:
        key = f"ocr:{url}"
        cached = cache.get(key)
        if cached is not None:
            text = cached
        else:
            text = ""
            try:
                response = context.request.get(url, timeout=20000)
                if response.ok:
                    body = response.body()
                    if len(body) <= MAX_IMAGE_BYTES:
                        text = ocr_image_bytes(body)
            except Exception as exc:
                print(f"[ocr] could not fetch {url}: {exc}")
            cache.set(key, text)

        if text:
            results.append(text)

    return " ".join(results)