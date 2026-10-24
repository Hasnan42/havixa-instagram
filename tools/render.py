"""Render each .slide in a post's slides.html to a 1080x1350 JPEG (Instagram 4:5).

Usage: python tools/render.py posts/2026-10-27-some-story
"""
import io
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

post = pathlib.Path(sys.argv[1]).resolve()
for old in post.glob("slide-*.jpg"):
    old.unlink()

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--allow-file-access-from-files", "--force-color-profile=srgb"])
    page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    page.goto((post / "slides.html").as_uri())
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)
    slides = page.locator(".slide").all()
    if not 2 <= len(slides) <= 20:
        sys.exit(f"Instagram carousels need 2 to 20 slides, found {len(slides)}")
    for i, slide in enumerate(slides, 1):
        png = slide.screenshot()
        Image.open(io.BytesIO(png)).convert("RGB").save(post / f"slide-{i}.jpg", quality=95, subsampling=0)
        print(f"slide-{i}.jpg")
    browser.close()
