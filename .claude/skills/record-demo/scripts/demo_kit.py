"""Record a silent demo video of `skill-atlas serve` with Playwright.

Usage from a scenes file (see demo_30s.py):

    with Demo(out_dir, port=8766) as d:
        d.goto("/")
        d.scan("JetBrains/ideavim")
        ...
    # on exit: <out>/demo.mp4 (scan waits trimmed), demo.gif (PR preview), sheet.png (frame check),
    # demo-moments.json (times of the d.mark() key moments in demo.mp4, see spec/demo-video.md)

Needs `pip install playwright && playwright install chromium`, plus ffmpeg on PATH.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Locator

# Playwright doesn't film the real mouse: draw one that follows mouse events.
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
  let pos = [640, 400];
  try { pos = JSON.parse(sessionStorage.getItem('__cur')) || pos; } catch {}
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


def cuts_from_markers(markers: list[list[float]], keep_head: float = 0.8,
                      keep_tail: float = 0.2) -> list[tuple[float, float]]:
    """Parts of each scan wait ``[start, end]`` to cut, keeping its head and tail."""
    return [(a + keep_head, b - keep_tail) for a, b in markers if b - a > keep_head + keep_tail]


def map_moments(moments: dict[str, float], cuts: list[tuple[float, float]]) -> dict[str, float]:
    """Moment times in the trimmed video. A moment inside a cut moves to where the cut was."""
    return {name: round(t - sum(min(b, t) - a for a, b in cuts if a < t), 3) for name, t in moments.items()}


def frozen_datetime(now: datetime) -> type[datetime]:
    """A ``datetime`` class whose ``now()`` always returns ``now``."""
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)
    return Frozen


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


class Demo:
    def __init__(self, out: Path | str, *, port: int = 8766, size=(1280, 800),
                 color_scheme: str = "dark", type_delay: int = 55, keep_wait: float = 0.8,
                 clock: datetime | None = None):
        """``clock`` freezes the server's time (scan times on the catalogue and stored pages)."""
        self.out = Path(out)
        self.clock = clock
        self.port, self.size, self.color_scheme = port, size, color_scheme
        self.type_delay, self.keep_wait = type_delay, keep_wait
        self.base = f"http://127.0.0.1:{port}"
        self.markers: list[list[float]] = []  # [start, end] of each scan wait, in video seconds
        self.moments: dict[str, float] = {}  # key moment name -> raw video seconds

    # --- lifecycle -------------------------------------------------------------------------
    def __enter__(self) -> "Demo":
        if port_in_use(self.port):
            raise SystemExit(f"port {self.port} is busy; pass another --port (don't kill what's there)")
        self.out.mkdir(parents=True, exist_ok=True)
        db = self.out / "demo.db"
        db.unlink(missing_ok=True)  # fresh DB → the catalogue starts empty
        from playwright.sync_api import sync_playwright
        from skill_atlas import store
        from skill_atlas.web import Handler, make_server

        # In-process server, so the clock can be frozen; no request log in the terminal.
        self._store_datetime = store.datetime
        if self.clock:
            store.datetime = frozen_datetime(self.clock)
        Handler.log_message = lambda *a: None
        self.server = make_server("127.0.0.1", self.port, db)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        w, h = self.size
        self.ctx = self.browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=2,
            color_scheme=self.color_scheme, record_video_dir=str(self.out / "video"),
            record_video_size={"width": w, "height": h})
        self.ctx.add_init_script(CURSOR_JS)
        self.page = self.ctx.new_page()
        self.t0 = time.monotonic()
        self.page.mouse.move(w / 2, h / 2)
        return self

    def __exit__(self, exc_type, *_):
        video = self.page.video.path()
        self.ctx.close(); self.browser.close(); self.pw.stop()
        self.server.shutdown(); self.server.server_close()
        from skill_atlas import store
        store.datetime = self._store_datetime
        if exc_type is None:
            shutil.move(video, self.out / "raw.webm")
            shutil.rmtree(self.out / "video", ignore_errors=True)
            (self.out / "markers.json").write_text(json.dumps(self.markers))
            (self.out / "moments.json").write_text(json.dumps(self.moments, indent=2) + "\n")
            self.finish()

    # --- actions ---------------------------------------------------------------------------
    def now(self) -> float:
        return time.monotonic() - self.t0

    def mark(self, name: str):
        """A key moment: CI screenshots it (spec/demo-video.md). Call it once the page has
        loaded and the pointer has stopped, and hold at least 1.5 s after it."""
        self.moments[name] = round(self.now(), 3)

    def hold(self, seconds: float):
        self.page.wait_for_timeout(int(seconds * 1000))

    def goto(self, path: str):
        self.page.goto(self.base + path)

    def move(self, target: Locator, dx=0.5, dy=0.5, steps=20):
        box = target.bounding_box()
        self.page.mouse.move(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy, steps=steps)

    def click(self, target: Locator, **kw):
        self.move(target, **kw)
        self.hold(0.25)
        self.page.mouse.down(); self.page.mouse.up()

    def nav_click(self, target: Locator, **kw):
        """Click a link and wait for the new page (a bare click races the navigation)."""
        with self.page.expect_navigation():
            self.click(target, **kw)
        self.page.wait_for_load_state("load")

    def type(self, text: str, delay: int | None = None):
        self.page.keyboard.type(text, delay=self.type_delay if delay is None else delay)

    def clear_field(self):
        self.page.keyboard.press("ControlOrMeta+A"); self.page.keyboard.press("Backspace")

    def scan(self, repo: str, *, via_slash: bool = False):
        """Type a repo into the scan form and submit; the clone wait is trimmed later."""
        if via_slash:
            self.page.locator("body").click(position={"x": 5, "y": self.size[1] - 5})
            self.page.keyboard.press("/")  # focuses the input and selects its text
            self.hold(0.3)
        else:
            self.page.locator("input[name=repo]").focus()
        self.type(repo)
        self.hold(0.5)
        start = self.now()
        with self.page.expect_navigation(timeout=180_000):
            self.page.keyboard.press("Enter")
        self.page.wait_for_load_state("load")
        self.markers.append([start, self.now()])

    def show_external(self, link: Locator, seconds: float = 4):
        """target=_blank links open a tab the video can't see: show the target in this tab."""
        self.move(link, dx=0.4)
        self.hold(1)
        href = link.get_attribute("href")
        self.page.goto(href, wait_until="domcontentloaded")
        self.hold(seconds)
        self.page.go_back(wait_until="load")

    def card(self, html_lines: list[str], seconds: float = 3.5, mark: str | None = None):
        """A full-screen terminal-style title card (outro, chapter title); ``mark`` names it
        as a key moment."""
        body = "<br>".join(html_lines)
        self.page.set_content(
            '<body style="margin:0;height:100vh;display:grid;place-items:center;background:#0d1117;'
            'font:500 34px/1.7 ui-monospace,Menlo,monospace;color:#e6edf3"><div>' + body + "</div></body>")
        if mark:
            self.mark(mark)
        self.hold(seconds)

    # --- post-processing -------------------------------------------------------------------
    def finish(self):
        d, keep_head, keep_tail = self.out, self.keep_wait, 0.2
        cuts = cuts_from_markers(self.markers, keep_head, keep_tail)
        (d / "demo-moments.json").write_text(json.dumps(map_moments(self.moments, cuts), indent=2) + "\n")
        expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cuts) or "0"
        ff = ["ffmpeg", "-y", "-loglevel", "error"]
        subprocess.run(ff + ["-i", str(d / "raw.webm"),
                             "-vf", f"fps=30,select='not({expr})',setpts=N/30/TB",
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                             "-movflags", "+faststart", str(d / "demo.mp4")], check=True)
        # GIF preview: GitHub strips <video> in PR descriptions but renders animated images.
        subprocess.run(ff + ["-i", str(d / "demo.mp4"), "-vf",
                             "fps=10,scale=800:-1:flags=lanczos,split[a][b];"
                             "[a]palettegen=max_colors=96:stats_mode=diff[p];"
                             "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                             str(d / "demo.gif")], check=True)
        # One frame every 2.5 s, tiled: read this image to check every scene rendered.
        subprocess.run(ff + ["-i", str(d / "demo.mp4"), "-vf", "fps=1/2.5,scale=640:-1,tile=3x6",
                             "-frames:v", "1", str(d / "sheet.png")], check=True)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(d / "demo.mp4")],
                             capture_output=True, text=True).stdout.strip()
        size = lambda f: f"{(d / f).stat().st_size / 1e6:.1f} MB"
        print(f"demo.mp4 {float(dur):.1f} s, {size('demo.mp4')}; demo.gif {size('demo.gif')}; "
              f"sheet.png; trimmed waits: {[(round(a, 1), round(b, 1)) for a, b in cuts]}")
