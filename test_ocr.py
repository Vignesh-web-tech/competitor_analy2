import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

from ocr import TESSERACT_AVAILABLE, ocr_image_bytes

if not TESSERACT_AVAILABLE:
    print("Tesseract is not available. Check the installation and the .env settings.")
    sys.exit(1)


def make_sample_image(path: str) -> None:
    img = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    draw.text((30, 30), "Pricing Plans: Free, Pro, Enterprise", fill="black", font=font)
    draw.text((30, 110), "Starts at 29 dollars per month", fill="black", font=font)
    img.save(path)


if len(sys.argv) < 2:
    source = "sample_ocr_test.png"
    make_sample_image(source)
    print(f"No image given. Created a sample image: {source}")
else:
    source = sys.argv[1]

if os.path.exists(source):
    with open(source, "rb") as f:
        data = f.read()
elif source.startswith(("http://", "https://")):
    request = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read()
else:
    print(f"File not found: {source}")
    sys.exit(1)

text = ocr_image_bytes(data)
print("OCR result:")
print(text if text else "(no readable text found)")