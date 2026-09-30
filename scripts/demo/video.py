"""Trim the demo recording, take screenshots at its key moments, and compare screenshots.

    python scripts/demo/video.py trim DIR
        DIR/raw.webm + markers.json + moments.json (from record.py)
        -> DIR/demo.mp4 + DIR/demo-moments.json (moment times in demo.mp4)
    python scripts/demo/video.py extract VIDEO MOMENTS OUT_DIR
        One PNG per moment: OUT_DIR/<name>.png
    python scripts/demo/video.py compare EXPECTED_DIR ACTUAL_DIR DIFF_DIR [options]
        Compares the PNGs, writes a diff image per failing frame, prints a report
        (also appended to $GITHUB_STEP_SUMMARY), exits 1 on any difference.

See spec/demo-video.md.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

# Keep this much of each scan wait so the "Scanning…" state stays visible.
KEEP_HEAD, KEEP_TAIL = 0.8, 0.2
FPS = 30
# Screenshots are taken this long after a moment starts: the recording sharpens for about
# a second after a page loads. Every moment lasts at least 1.5 s.
SETTLE = 1.2
# A pixel has changed when a colour channel differs by more than this (0-255): video
# compression noise stays below it.
CHANNEL_THRESHOLD = 40
# A frame fails when more pixels than this have changed. Two takes differ by 0 pixels;
# a one-character change in the page footer changes ~13.
MAX_CHANGED_PIXELS = 5


def cuts_from_markers(markers: list[list[float]]) -> list[tuple[float, float]]:
    """Parts of each scan wait ``[start, end]`` to cut from the raw video."""
    return [(a + KEEP_HEAD, b - KEEP_TAIL) for a, b in markers if b - a > KEEP_HEAD + KEEP_TAIL]


def map_moments(moments: dict[str, float], cuts: list[tuple[float, float]]) -> dict[str, float]:
    """Moment times in the trimmed video. A moment inside a cut moves to where the cut was."""
    return {
        name: round(t - sum(min(b, t) - a for a, b in cuts if a < t), 3)
        for name, t in moments.items()
    }


def trim(d: Path) -> None:
    markers = json.loads((d / "markers.json").read_text())
    moments = json.loads((d / "moments.json").read_text())
    cuts = cuts_from_markers(markers)
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cuts) or "0"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(d / "raw.webm"),
         "-vf", f"fps={FPS},select='not({expr})',setpts=N/{FPS}/TB",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart",
         str(d / "demo.mp4")],
        check=True,
    )
    (d / "demo-moments.json").write_text(json.dumps(map_moments(moments, cuts), indent=2) + "\n")


def extract(video: Path, moments_file: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, t in json.loads(moments_file.read_text()).items():
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t + SETTLE:.3f}", "-i", str(video),
             "-frames:v", "1", str(out / f"{name}.png")],
            check=True,
        )


@dataclass
class FrameResult:
    name: str
    changed: int | None  # None: the frame is missing on one side or the sizes differ
    total: int
    ok: bool
    note: str = ""


def diff_images(
    expected: Image.Image, actual: Image.Image, channel_threshold: int = CHANNEL_THRESHOLD,
) -> tuple[int, Image.Image]:
    """Number of changed pixels, and a mask of them (255 = changed)."""
    diff = ImageChops.difference(expected.convert("RGB"), actual.convert("RGB"))
    r, g, b = (c.point(lambda v: 255 if v > channel_threshold else 0) for c in diff.split())
    mask = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return mask.histogram()[255], mask


def diff_picture(expected: Image.Image, actual: Image.Image, mask: Image.Image) -> Image.Image:
    """Expected | actual | actual dimmed with the changed pixels in red."""
    w, h = expected.size
    marked = Image.blend(actual.convert("RGB"), Image.new("RGB", (w, h)), 0.6)
    marked.paste(Image.new("RGB", (w, h), (255, 0, 0)), mask=mask)
    out = Image.new("RGB", (w * 3, h))
    for i, img in enumerate((expected.convert("RGB"), actual.convert("RGB"), marked)):
        out.paste(img, (w * i, 0))
    return out


def compare_dirs(
    expected_dir: Path, actual_dir: Path, diff_dir: Path, *,
    channel_threshold: int = CHANNEL_THRESHOLD, max_changed_pixels: int = MAX_CHANGED_PIXELS,
) -> list[FrameResult]:
    names = sorted({p.stem for p in expected_dir.glob("*.png")} | {p.stem for p in actual_dir.glob("*.png")})
    results = []
    for name in names:
        exp_path, act_path = expected_dir / f"{name}.png", actual_dir / f"{name}.png"
        if not exp_path.exists():
            results.append(FrameResult(name, None, 0, False, "no expected screenshot"))
            continue
        if not act_path.exists():
            results.append(FrameResult(name, None, 0, False, "no screenshot taken"))
            continue
        exp, act = Image.open(exp_path), Image.open(act_path)
        if exp.size != act.size:
            results.append(FrameResult(name, None, 0, False, f"size {act.size} != expected {exp.size}"))
            continue
        changed, mask = diff_images(exp, act, channel_threshold)
        ok = changed <= max_changed_pixels
        if not ok:
            diff_dir.mkdir(parents=True, exist_ok=True)
            diff_picture(exp, act, mask).save(diff_dir / f"{name}.png")
        results.append(FrameResult(name, changed, exp.size[0] * exp.size[1], ok))
    return results


def report(results: list[FrameResult], title: str, max_changed_pixels: int) -> str:
    failed = sum(not r.ok for r in results)
    status = "all match" if results and not failed else f"{failed} of {len(results)} differ"
    if not results:
        status = "no screenshots"
    lines = [f"### {title}: {status}", "",
             f"A frame fails when more than {max_changed_pixels} pixels changed.", "",
             "| Frame | Changed pixels | % | Result |", "|---|---:|---:|---|"]
    for r in results:
        if r.changed is None:
            lines.append(f"| {r.name} | – | – | FAIL: {r.note} |")
        else:
            pct = 100 * r.changed / r.total
            lines.append(f"| {r.name} | {r.changed} | {pct:.3f} | {'PASS' if r.ok else 'FAIL'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trim")
    t.add_argument("dir", type=Path)
    e = sub.add_parser("extract")
    e.add_argument("video", type=Path)
    e.add_argument("moments", type=Path)
    e.add_argument("out", type=Path)
    c = sub.add_parser("compare")
    c.add_argument("expected", type=Path)
    c.add_argument("actual", type=Path)
    c.add_argument("diff", type=Path)
    c.add_argument("--channel-threshold", type=int, default=CHANNEL_THRESHOLD)
    c.add_argument("--max-changed-pixels", type=int, default=MAX_CHANGED_PIXELS)
    c.add_argument("--title", default="Demo video screenshots")
    args = ap.parse_args(argv)

    if args.cmd == "trim":
        trim(args.dir)
    elif args.cmd == "extract":
        extract(args.video, args.moments, args.out)
    else:
        results = compare_dirs(args.expected, args.actual, args.diff,
                               channel_threshold=args.channel_threshold,
                               max_changed_pixels=args.max_changed_pixels)
        text = report(results, args.title, args.max_changed_pixels)
        print(text)
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(summary, "a") as f:
                f.write(text + "\n")
        return 0 if results and all(r.ok for r in results) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
