"""Demo video screenshot check (spec/demo-video.md): trimming, comparison, committed baseline."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "tests" / "demo_frames"
MOMENTS = ROOT / "docs" / "demo-moments.json"

_spec = importlib.util.spec_from_file_location("demo_video", ROOT / "scripts" / "demo" / "video.py")
video = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = video  # dataclasses look their module up
_spec.loader.exec_module(video)

KEY_MOMENTS = [
    "01-home-empty", "02-ideavim-result", "03-filter-commit", "04-kotlin-result",
    "05-catalogue", "06-stored-ideavim", "07-similar", "08-outro",
]


def frame(color=(12, 14, 18), size=(64, 40)) -> Image.Image:
    return Image.new("RGB", size, color)


def save(d: Path, name: str, img: Image.Image) -> None:
    d.mkdir(parents=True, exist_ok=True)
    img.save(d / f"{name}.png")


# --- Trimming --------------------------------------------------------------------------------

def test_scan_waits_keep_head_and_tail():
    assert video.cuts_from_markers([[2.0, 10.0]]) == [(2.8, 9.8)]


def test_short_scan_waits_are_not_cut():
    assert video.cuts_from_markers([[2.0, 2.9]]) == []


def test_moments_shift_by_the_cuts_before_them():
    cuts = [(2.0, 5.0), (10.0, 11.0)]
    moments = {"before": 1.0, "between": 7.0, "after": 12.0}
    assert video.map_moments(moments, cuts) == {"before": 1.0, "between": 4.0, "after": 8.0}


def test_moment_inside_a_cut_moves_to_the_cut():
    assert video.map_moments({"m": 3.0}, [(2.0, 5.0)]) == {"m": 2.0}


# --- Comparison ------------------------------------------------------------------------------

def test_identical_frames_pass(tmp_path):
    save(tmp_path / "exp", "01-a", frame())
    save(tmp_path / "act", "01-a", frame())
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert (r.name, r.changed, r.ok) == ("01-a", 0, True)
    assert not (tmp_path / "diff").exists()


def test_noise_below_channel_threshold_passes(tmp_path):
    save(tmp_path / "exp", "01-a", frame((100, 100, 100)))
    save(tmp_path / "act", "01-a", frame((100 + video.CHANNEL_THRESHOLD, 100, 100)))
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert r.ok and r.changed == 0


def test_few_changed_pixels_pass(tmp_path):
    act = frame()
    for x in range(video.MAX_CHANGED_PIXELS):
        act.putpixel((x, 0), (255, 255, 255))
    save(tmp_path / "exp", "01-a", frame())
    save(tmp_path / "act", "01-a", act)
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert r.ok and r.changed == video.MAX_CHANGED_PIXELS


def test_changed_region_fails_and_writes_diff(tmp_path):
    act = frame()
    ImageDraw.Draw(act).rectangle((10, 10, 19, 19), fill=(255, 255, 255))
    save(tmp_path / "exp", "01-a", frame())
    save(tmp_path / "act", "01-a", act)
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert (r.changed, r.ok) == (100, False)
    diff = Image.open(tmp_path / "diff" / "01-a.png")
    assert diff.size == (64 * 3, 40)
    assert diff.getpixel((64 * 2 + 15, 15)) == (255, 0, 0)  # changed pixel marked red
    assert diff.getpixel((64 * 2 + 1, 1)) != (255, 0, 0)


@pytest.mark.parametrize("side, note", [("exp", "no screenshot taken"), ("act", "no expected screenshot")])
def test_missing_frame_fails(tmp_path, side, note):
    save(tmp_path / side, "01-a", frame())
    (tmp_path / ("act" if side == "exp" else "exp")).mkdir()
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert (r.ok, r.note) == (False, note)


def test_size_mismatch_fails(tmp_path):
    save(tmp_path / "exp", "01-a", frame(size=(64, 40)))
    save(tmp_path / "act", "01-a", frame(size=(32, 20)))
    [r] = video.compare_dirs(tmp_path / "exp", tmp_path / "act", tmp_path / "diff")
    assert not r.ok and r.note.startswith("size")


def test_cli_reports_every_frame_and_fails_on_difference(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    save(tmp_path / "exp", "01-a", frame())
    save(tmp_path / "act", "01-a", frame())
    save(tmp_path / "exp", "02-b", frame())
    save(tmp_path / "act", "02-b", frame((255, 255, 255)))
    code = video.main(["compare", str(tmp_path / "exp"), str(tmp_path / "act"), str(tmp_path / "diff")])
    out = capsys.readouterr().out
    assert code == 1
    assert "1 of 2 differ" in out
    assert "| 01-a | 0 | 0.000 | PASS |" in out
    assert "| 02-b | 2560 | 100.000 | FAIL |" in out
    assert summary.read_text().strip() == out.strip()


def test_cli_passes_when_all_match(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    save(tmp_path / "exp", "01-a", frame())
    save(tmp_path / "act", "01-a", frame())
    assert video.main(["compare", str(tmp_path / "exp"), str(tmp_path / "act"), str(tmp_path / "d")]) == 0


def test_cli_fails_without_frames(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    (tmp_path / "exp").mkdir()
    (tmp_path / "act").mkdir()
    assert video.main(["compare", str(tmp_path / "exp"), str(tmp_path / "act"), str(tmp_path / "d")]) == 1


# --- Committed baseline ----------------------------------------------------------------------

def test_baseline_has_every_key_moment():
    moments = json.loads(MOMENTS.read_text())
    assert list(moments) == KEY_MOMENTS
    assert sorted(p.stem for p in FRAMES.glob("*.png")) == KEY_MOMENTS
    times = list(moments.values())
    assert times == sorted(times)


def test_baseline_frames_are_full_size():
    for p in FRAMES.glob("*.png"):
        assert Image.open(p).size == (1280, 800), p.name
