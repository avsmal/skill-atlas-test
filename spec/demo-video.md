# Demo video screenshot check

`docs/demo.mp4` is the 30-second web UI demo (script: [docs/demo-script.md](../docs/demo-script.md)).
On every pull request, CI re-records it, takes a screenshot at each **key moment**, and compares the
screenshots with the reference screenshots in `tests/demo_frames/`. A visible change to any page in the
demo fails CI until the baseline is updated on purpose.

## Recording

`scripts/demo/record.py OUT_DIR` drives headless Chromium (Playwright, pinned in the `demo` extra of
`pyproject.toml`) with a 1280×800 viewport, device scale factor 2, and a dark color scheme. It draws a
fake mouse pointer, because Playwright doesn't render one.

The web server runs in-process on a fresh DB in `OUT_DIR`, on a free port. Its clock is frozen at
`2026-09-30 14:40 UTC`, so the scan times on the catalogue and stored pages never change.

The scans read **pinned repositories**. `scripts/demo/pin-repos.sh DIR` creates local mirrors that hold
only the skill files at these commits:

| Repository | Commit |
|---|---|
| JetBrains/ideavim | `7bd8f1315c8abd5c7371c996386c334f683d878d` |
| JetBrains/kotlin | `848b4009281f9043612814e22077289d07f5063e` |

It also writes `DIR/gitconfig` with `url.<mirror>.insteadOf https://github.com/<repo>` rules. With
`GIT_CONFIG_GLOBAL=DIR/gitconfig`, skill-atlas clones the mirrors, while the pages still show the
GitHub URLs and commits. It needs the network only to create the mirrors.

`scripts/demo/video.py trim OUT_DIR` cuts the middle of every scan wait longer than 1 s, keeping
0.8 s of *Scanning…* and 0.2 s before the result. It encodes `OUT_DIR/demo.mp4` (H.264, 30 fps) and
writes `OUT_DIR/demo-moments.json`, which holds the key moments' times in the trimmed video.

## Key moments

Each moment begins once the page has loaded and the pointer has stopped. The page then stays still
for at least 1.5 s. The screenshot is taken 1.2 s into the moment, because the recording sharpens for
about a second after a page loads.

| Moment | On screen |
|---|---|
| `01-home-empty` | Home page, empty catalogue (*No repositories yet*) |
| `02-ideavim-result` | Scan result for JetBrains/ideavim, pointer on the `$ skill-atlas scan` title |
| `03-filter-commit` | Filter `commit`: only `changelog` and `git-workflow` |
| `04-kotlin-result` | Scan result for JetBrains/kotlin |
| `05-catalogue` | Catalogue: `2 repositories · 12 skills` |
| `06-stored-ideavim` | Stored JetBrains/ideavim page |
| `07-similar` | *Similar to extensions-api-migration*, top hit `analysis-api-create-cherry-pick-issue` 18.8 % (JetBrains/kotlin) |
| `08-outro` | Install card: `pip install -e .`, `skill-atlas serve` |

`scripts/demo/video.py extract VIDEO MOMENTS OUT_DIR` writes `OUT_DIR/<moment>.png` for every moment.

## Comparison

`scripts/demo/video.py compare EXPECTED_DIR ACTUAL_DIR DIFF_DIR` compares the PNGs with the same names.

- A pixel **changed** when any color channel differs by more than **40** (`--channel-threshold`).
  Video compression noise stays below that.
- A frame **fails** when more than **5** pixels changed (`--max-changed-pixels`). Two recordings on
  the same machine differ by 0 pixels. Changing one character in the page footer changes about 13.
- A frame also fails when it is missing on either side or the sizes differ. If there are no frames
  at all, the check fails too.
- For each failing frame, it writes `DIFF_DIR/<moment>.png`: the expected frame, the actual frame,
  and the actual frame dimmed with changed pixels in red, side by side.
- It prints a Markdown table (frame, changed pixels, %, PASS/FAIL) and appends it to
  `$GITHUB_STEP_SUMMARY` when that is set. The exit code is 1 on any failure, 0 otherwise.

## Baseline

The baseline is committed:
- `docs/demo.mp4`: recorded by CI on Linux, not on a developer machine, because fonts render differently.
- `docs/demo-moments.json`
- `tests/demo_frames/<moment>.png`: extracted from `docs/demo.mp4` at those moments.
- `docs/demo.gif`: an 800 px, 10 fps copy of the video for the README and PR descriptions.

`tests/test_demo_video.py` checks that the baseline has exactly the key moments above, in order, and
that every frame is 1280×800.

To accept a new recording (after an intended UI change, or a new Playwright or runner image), run:

```bash
scripts/demo/update-baseline.sh <run id>
```

It downloads that CI run's `demo-video` artifact, copies the video, moments and frames into place,
and rebuilds the GIF. Look at the frames and commit them.

## CI

The `demo-video` job in `.github/workflows/tests.yml`:
- Runs once per pull request run, on `ubuntu-24.04` with Python 3.14. It doesn't run on pushes to
  `main` or on manual runs, and it's skipped like `pytest` when only Markdown changed (see
  [cli.md](cli.md) → *Continuous integration*).
- Installs ffmpeg, the `demo` extra and Chromium, then pins the repositories.
- **Checks the baseline:** extracts frames from the committed `docs/demo.mp4` and compares them with
  `tests/demo_frames/`, so the PNGs can't drift from the video.
- **Records and compares:** records, trims and extracts, then compares the new frames with
  `tests/demo_frames/`. It records even if the baseline check failed.
- Always uploads the artifact `demo-video`: `demo.mp4`, `demo-moments.json`, `frames/`, and the
  `diff/` and `baseline-diff/` images of failing frames.
