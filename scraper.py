import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from cache import cache
from config import MAX_PAGES_PER_SITE, MIN_TEXT_CHARS, USER_AGENT
from ocr import TESSERACT_AVAILABLE, ocr_images

SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".mp4", ".mp3", ".css", ".js", ".xml", ".json",
)

SKIP_IMAGE_EXTENSIONS = (".svg", ".gif", ".ico")
SKIP_IMAGE_HINTS = ("sprite", "favicon", "pixel", "tracking", "spacer", "blank", "avatar", "emoji")

# Pages that usually matter most for competitor analysis are crawled first.
PRIORITY_HINTS = (
    "pricing", "price", "plans", "features", "product", "solutions",
    "integrations", "customers", "case-stud", "about", "compare", "security",
)


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _priority(url: str) -> int:
    lowered = url.lower()
    return 0 if any(hint in lowered for hint in PRIORITY_HINTS) else 1


def _extract_images(soup, base_url: str) -> list:
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        src = src.strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(base_url, src)
        if not absolute.startswith(("http://", "https://")):
            continue
        lowered = absolute.lower().split("?")[0]
        if lowered.endswith(SKIP_IMAGE_EXTENSIONS):
            continue
        if any(hint in lowered for hint in SKIP_IMAGE_HINTS):
            continue
        if absolute not in images:
            images.append(absolute)
    return images


def extract_page(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if _host(absolute) != _host(base_url):
            continue
        if absolute.lower().endswith(SKIP_EXTENSIONS):
            continue
        if absolute not in links:
            links.append(absolute)

    images = _extract_images(soup, base_url)

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

    return {
        "url": base_url,
        "title": title,
        "text": text,
        "links": links,
        "images": images,
    }


def fetch_page(context, url: str, force: bool = False):
    """Return page data from cache if available, otherwise scrape it."""
    key = f"page:v2:{url}"
    if not force:
        cached = cache.get(key)
        if cached is not None:
            return cached

    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)  # let client-side content render
        html = page.content()
    except Exception as exc:
        print(f"[scraper] failed to load {url}: {exc}")
        return None
    finally:
        page.close()

    data = extract_page(html, url)
    cache.set(key, data)
    return data


def crawl_site(start_url: str, max_pages: int = MAX_PAGES_PER_SITE, force: bool = False) -> list:
    """Crawl a website (same domain only) and return a list of pages with text (including OCR text from images)."""
    start_url = normalize_url(start_url)
    visited = set()
    queue = [start_url]
    pages = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        try:
            while queue and len(pages) < max_pages:
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)

                data = fetch_page(context, url, force=force)
                if not data:
                    continue

                text = data["text"]
                if TESSERACT_AVAILABLE and data.get("images"):
                    image_text = ocr_images(context, data["images"])
                    if image_text:
                        text = f"{text} [Text found in images on this page: {image_text}]"

                if len(text) >= MIN_TEXT_CHARS:
                    pages.append({"url": data["url"], "title": data["title"], "text": text})

                for link in data["links"]:
                    if link not in visited and link not in queue:
                        queue.append(link)
                queue.sort(key=_priority)
        finally:
            context.close()
            browser.close()

    return pages