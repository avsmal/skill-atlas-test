---
name: record-demo
description: Record a silent screen video of the skill-atlas web UI (`skill-atlas serve`) with Playwright — scripted scenes, trimmed scan waits, MP4 plus a GIF preview for PR descriptions. Use when asked to record, re-record or update the demo video (docs/demo.mp4), make a new demo cut, or show the web UI in a PR.
---

# Record a web UI demo video

Produces a page-only MP4 of the web UI, driven by a scenes file, from a fresh DB. The agent can't
record a voice-over: videos are silent, and the narration lives in
[`docs/demo-script.md`](../../../docs/demo-script.md).

Files:
- `scripts/demo_kit.py`: the `Demo` recorder (server, fake cursor, clicks, scans, cards, trimming,
  GIF, frame sheet). Read its docstrings before writing scenes.
- `scripts/demo_30s.py`: the scenes behind `docs/demo.mp4` (~30 s). Copy it for a new cut.

**`docs/demo.mp4` is also a CI regression test** ([spec/demo-video.md](../../../spec/demo-video.md)).
On every PR, CI re-records it with `demo_30s.py` on Linux, with the demo repos pinned, and compares
screenshots at its `d.mark()` key moments with `tests/demo_frames/`. Don't commit a local recording
as `docs/demo.mp4`: macOS renders differently. After changing the scenes or the UI, push, then
accept CI's recording with `scripts/demo/update-baseline.sh <run id>`. Keep every `d.mark()` at a
settled page with at least 1.5 s of hold after it.

## 1. Plan the cut

- Start from `docs/demo-script.md` (scenes, repos, voice-over). Ask the user how long the video
  should be; a ~30 s cut fits 5–6 scenes.
- Dry-run the scans first (`skill-atlas scan <repo> --db <scratch>/probe.db`) and use the real
  numbers: skill counts, filter keywords that narrow the list, and a *Similar skills* target whose
  top match is in **another** repo (JetBrains/ideavim's `extensions-api-migration` → kotlin, 18.8 %
  on 2026-09-30). Repos change: recheck before recording.

## 2. Set up (ask first)

Playwright is only in the optional `demo` extra (pinned: another Chromium renders differently).
Installing it downloads the package (~40 MB) and Chromium (~150 MB), so **ask the user before**:

```bash
. .venv/bin/activate
pip install -e '.[demo]' && playwright install chromium
```

To record the same content as CI, pin the repos first:
`scripts/demo/pin-repos.sh <scratchpad>/pins && export GIT_CONFIG_GLOBAL=<scratchpad>/pins/gitconfig`.

`ffmpeg`/`ffprobe` must be on `PATH` (`brew install ffmpeg`).

## 3. Record

```bash
python .claude/skills/record-demo/scripts/demo_30s.py <scratchpad>/take1 --port 8766
```

Output in `<out>`: `demo.mp4` (scan waits trimmed to 0.8 s of *Scanning…*), `demo.gif` (800 px,
10 fps), `sheet.png` (a frame every 2.5 s), `demo-moments.json` (key moments in `demo.mp4`), plus
`raw.webm`, `markers.json`, `moments.json` and `demo.db`.
Write recordings to the scratchpad, not the repo, until the user wants one committed.

**Check `sheet.png` before showing the video** (read the image): every scene present, no error page,
no half-loaded frame. Send the MP4 to the user and wait for feedback before committing.

## 4. Commit (when asked)

- One branch/PR as usual (`AGENTS.md`). The committed video is `docs/demo.mp4`; link it from
  `README.md` and `docs/demo-script.md`, and update the numbers in `demo-script.md` if they changed.
- **Showing it in the PR description:** GitHub strips `<video>` tags, and only its own upload
  attachments play inline (`gh` can't create those). Commit `docs/demo.gif` too and embed it as a
  link to the MP4, with URLs **pinned to the commit SHA** so they survive branch deletion:
  `[![demo](https://github.com/<owner>/<repo>/raw/<sha>/docs/demo.gif)](https://github.com/<owner>/<repo>/raw/<sha>/docs/demo.mp4)`.
  Check it renders: `gh api markdown -f mode=gfm -f text="$(gh pr view <n> --json body -q .body)"`.
- Fill in the PR template; under *Known issues* mention that the video goes stale when the UI or
  the demo repos change.

## Pitfalls (all hit while building this)

- **Busy port:** something else may own the port (8000 was taken once). `Demo` refuses a busy
  port; pick another with `--port`. Never kill a process you didn't start. The server runs
  in-process (so `clock=` can freeze scan times).
- **Navigation race:** after a click on a link, use `nav_click()`, not `click()` +
  `wait_for_load_state()`, which returns immediately on the old page.
- **No real cursor** in Playwright videos: `demo_kit` injects a drawn one (init script, persists
  its position across pages via `sessionStorage`). Move with `move()`/`click()` so it glides.
- **`target=_blank` links** (GitHub paths) open a tab the video doesn't record: use
  `show_external()`, which shows the target in the same tab and comes back.
- **Clone time varies** (kotlin: 4 s once, 20–34 s later). Waits inside `scan()` are cut
  automatically; waits anywhere else are not, so always scan through `scan()`.
- A fresh DB each run keeps the catalogue deterministic; scanning a repo again moves it to the top.
- The last scene runs a little longer than its `hold()` (the video ends when the context closes).
