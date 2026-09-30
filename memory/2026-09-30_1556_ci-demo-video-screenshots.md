# PR #17 — CI: re-record the demo video and compare key-moment screenshots

- **Date/time:** 2026-09-30, discussion started ~15:30 UTC, PR opened 15:56 UTC
- **Branch:** `ci/demo-video-screenshots`
- **PR:** https://github.com/avsmal/skill-atlas-test/pull/17

## What was asked
- Turn `docs/demo.mp4` into a test. Store 5–10 screenshots of its key moments in the repo. On every
  PR, CI records the video once, takes screenshots at the same moments, compares them with the stored
  ones, and fails with a report when they differ.
- In planning, the user chose two options: re-record the baseline on CI's Linux runner, and pin the
  demo repos to the video's commits.

## What was decided / built
- **Linux baseline.** The macOS-recorded video can't match a Linux re-recording, because fonts
  render differently. `docs/demo.mp4`, `docs/demo.gif`, `docs/demo-moments.json` and
  `tests/demo_frames/*.png` now come from a CI run's `demo-video` artifact, installed with
  `scripts/demo/update-baseline.sh <run id>`.
- **Pinned repos.** `scripts/demo/pin-repos.sh` builds local mirrors:
  - ideavim is pinned at `7bd8f1315c8a` and kotlin at `848b4009281f`. Kotlin's commit came from the
    DB of the recording behind PR #14. `demo-script.md` says `d3c2339829f4`, but that is the
    3-minute dry run.
  - Each mirror is blobless plus only the SKILL.md blobs. Upload-pack won't lazy-fetch, so the blobs
    are pre-fetched by a sparse checkout.
  - `GIT_CONFIG_GLOBAL` points at a gitconfig with `url.insteadOf` rules, so pages still show
    github.com.
- **Frozen clock.** `Demo(clock=…)` patches `skill_atlas.store.datetime`, because the catalogue and
  stored pages show scan times. That needs an in-process server, so the kit's subprocess server
  became `make_server` in a thread.
- **Recorder reuse.** PR #16 (the record-demo skill) merged while this PR was open, with the same
  recorder. `demo_kit` gained `mark()`, `clock=`, `demo-moments.json` and `cuts_from_markers` /
  `map_moments`. Playwright is imported lazily, so the tests load the kit without it. My own
  `scripts/demo/record.py` was dropped. `scripts/demo/video.py` does extract and compare only.
- **8 moments.** Each one is a settled page with at least 1.5 s of hold after it. The screenshot is
  taken 1.2 s in: at 0.5 s the WebM was still sharpening after a navigation, and two takes differed
  by 3.6k pixels on `07-similar`.
- **Thresholds.** A pixel counts as changed when a channel differs by more than 40; a frame fails
  when more than 5 pixels changed.
  - On macOS, two takes differed by 0 pixels (1 on the first frame).
  - A one-character footer change (`.` → `!`) changed 13 pixels, so a budget of 500 would have
    missed it.
  - On CI, two runs of the baseline commit (36743922096 and its rerun) had 0 changed pixels on
    every frame.
- **CI job.** `demo-video` runs on `ubuntu-24.04`, only on `pull_request`, outside the OS matrix, and
  is skipped for Markdown-only changes like `pytest`.
  - It first checks that `tests/demo_frames` matches `docs/demo.mp4`.
  - It records even if that check fails, so the bootstrap run still produces an artifact.
- Playwright is pinned (`demo` extra, 1.63.0) because a new Chromium would change the frames.

## Context
- A PR that conflicts with `main` gets **no** `pull_request` run at all, not a failed one. The first
  push showed no checks until `main` (PR #16) was merged in.
- The first `demo-video` run hung in `apt-get install ffmpeg`: the Azure Ubuntu mirror stalled
  for 15+ minutes. The job now avoids apt entirely:
  - ffmpeg comes from `imageio-ffmpeg` on PyPI (static, no ffprobe).
  - Chromium is installed with `playwright install chromium`, without `--with-deps`.
  - A 20-minute job timeout and an 8-minute install timeout are set.
- The baseline came from the `demo-video` artifact of run 36743539416. Linux fonts wrap the home
  headline onto two lines.
- The workflow push still needs SSH, because the HTTPS token lacks the `workflow` scope.

## Stale records removed
- `2026-09-30_1531_docs-record-demo-skill.md`:
  - "Playwright stays out of `pyproject.toml`": it is now in the optional `demo` extra.
  - "No tests in CI": the recording is now a CI test.
