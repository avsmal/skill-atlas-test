"""Record the 30-second web UI demo (docs/demo.mp4) as a silent screen video.

Usage: python scripts/demo/record.py OUT_DIR

Runs the web server in-process on a fresh DB with a frozen clock, drives Chromium with
Playwright through the scenes in spec/demo-video.md and writes to OUT_DIR:
- raw.webm      the untrimmed recording
- markers.json  scan waits to cut out, as [start, end] seconds in raw.webm
- moments.json  key moments (screenshot points), as {name: seconds in raw.webm}

Pin the repositories first (scripts/demo/pin-repos.sh), or the scans read live GitHub.
Then `python scripts/demo/video.py trim OUT_DIR` produces demo.mp4.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from skill_atlas import store
from skill_atlas.web import make_server

W, H = 1280, 800
# Scan time shown on the catalogue and stored pages.
FROZEN_NOW = datetime(2026, 9, 30, 14, 40, tzinfo=timezone.utc)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW.astimezone(tz) if tz else FROZEN_NOW.replace(tzinfo=None)


# Playwright doesn't render the mouse pointer, so draw one that follows mouse events.
CURSOR_JS = """
(() => {
  if (window.__cursor) return;
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;'
    + 'pointer-events:none;transform:translate(-3px,-2px);transition:transform .08s';
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 11-7 1-4 7z" '
    + 'fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  const add = () => document.body && document.body.appendChild(c);
  add() || document.addEventListener('DOMContentLoaded', add);
  const pos = JSON.parse(sessionStorage.getItem('__cur') || '[640,400]');
  c.style.left = pos[0] + 'px'; c.style.top = pos[1] + 'px';
  addEventListener('mousemove', e => {
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
    try { sessionStorage.setItem('__cur', JSON.stringify([e.clientX, e.clientY])); } catch {}
  }, true);
  addEventListener('mousedown', () => c.style.transform = 'translate(-3px,-2px) scale(.8)', true);
  addEventListener('mouseup', () => c.style.transform = 'translate(-3px,-2px)', true);
  window.__cursor = c;
})();
"""

OUTRO_HTML = """<body style="margin:0;height:100vh;display:grid;place-items:center;
  background:#0d1117;font:500 34px/1.7 ui-monospace,Menlo,monospace;color:#e6edf3">
  <div><span style="color:#7ee787">$</span> pip install -e .<br>
  <span style="color:#7ee787">$</span> skill-atlas serve<br>
  <span style="color:#8b949e;font-size:22px">skill-atlas web UI on http://127.0.0.1:8000/</span>
  </div></body>"""


class Recorder:
    def __init__(self, page):
        self.page = page
        self.t0 = time.monotonic()
        self.markers: list[list[float]] = []
        self.moments: dict[str, float] = {}

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    def mark(self, name: str) -> None:
        """A key moment: the page is settled and stays still for at least a second."""
        self.moments[name] = self.now()

    def hold(self, s: float) -> None:
        self.page.wait_for_timeout(int(s * 1000))

    def move_to(self, locator, dx=0.5, dy=0.5, steps=25) -> None:
        box = locator.bounding_box()
        self.page.mouse.move(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy, steps=steps)

    def click(self, locator, **kw) -> None:
        self.move_to(locator, **kw)
        self.page.wait_for_timeout(250)
        self.page.mouse.down()
        self.page.mouse.up()

    def nav_click(self, locator, **kw) -> None:
        with self.page.expect_navigation():
            self.click(locator, **kw)
        self.page.wait_for_load_state("load")

    def scan(self, repo: str) -> None:
        """Type ``repo``, submit, and record the wait so it can be trimmed."""
        self.page.keyboard.type(repo, delay=55)
        self.hold(0.5)
        start = self.now()
        with self.page.expect_navigation(timeout=180_000):
            self.page.keyboard.press("Enter")
        self.page.wait_for_load_state("load")
        self.markers.append([start, self.now()])


def play(r: Recorder, base: str) -> None:
    page = r.page
    page.goto(base + "/")
    page.mouse.move(640, 400)
    # Home, empty catalogue
    r.mark("01-home-empty")
    r.hold(2)
    page.locator("input[name=repo]").focus()
    r.scan("JetBrains/ideavim")
    # Result: CLI-identical output
    r.move_to(page.locator(".term__cmd").first, dx=0.3, steps=15)
    r.mark("02-ideavim-result")
    r.hold(2.5)
    # Filter
    r.click(page.locator("[data-filter]"))
    page.keyboard.type("commit", delay=90)
    r.mark("03-filter-commit")
    r.hold(2)
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.press("Backspace")
    # Second repository via "/"
    page.locator("body").click(position={"x": 5, "y": H - 5})
    page.keyboard.press("/")
    r.hold(0.3)
    r.scan("JetBrains/kotlin")
    r.mark("04-kotlin-result")
    r.hold(1.5)
    # Catalogue, then the stored ideavim page
    r.nav_click(page.locator("a.brand"))
    r.mark("05-catalogue")
    r.hold(2)
    r.nav_click(page.locator("#catalogue a[href*='ideavim']").first, dx=0.2)
    r.mark("06-stored-ideavim")
    r.hold(1.5)
    # Similar skills
    r.nav_click(page.locator("pre a[href*='extensions-api-migration']").first, dx=0.3)
    r.move_to(page.locator("a[href*='/stored?repo='][href*='kotlin']").first, steps=20)
    r.mark("07-similar")
    r.hold(4)
    # Install card
    page.set_content(OUTRO_HTML)
    r.mark("08-outro")
    r.hold(3.5)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    db = out / "demo.db"
    db.unlink(missing_ok=True)

    store.datetime = _FrozenDatetime
    server = make_server("127.0.0.1", 0, db)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H}, device_scale_factor=2,
            color_scheme="dark", record_video_dir=str(out / "video"),
            record_video_size={"width": W, "height": H},
        )
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        r = Recorder(page)
        play(r, base)
        video = page.video.path()
        ctx.close()
        browser.close()

    server.shutdown()
    shutil.move(video, out / "raw.webm")
    shutil.rmtree(out / "video", ignore_errors=True)
    (out / "markers.json").write_text(json.dumps(r.markers) + "\n")
    (out / "moments.json").write_text(json.dumps(r.moments, indent=2) + "\n")
    print("scan waits:", r.markers)
    print("moments:", r.moments)


if __name__ == "__main__":
    main()
