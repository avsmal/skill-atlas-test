"""Scenes for docs/demo.mp4: the ~30 s cut of docs/demo-script.md.

    python .claude/skills/record-demo/scripts/demo_30s.py <out-dir> [--port 8766]
"""
import argparse
from datetime import datetime, timezone

from demo_kit import Demo

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--port", type=int, default=8766)
args = ap.parse_args()

# Frozen scan time: the key-moment screenshots CI compares must not change (spec/demo-video.md).
CLOCK = datetime(2026, 9, 30, 14, 40, tzinfo=timezone.utc)

with Demo(args.out, port=args.port, clock=CLOCK) as d:
    p = d.page
    # 0:00 Home, then scan ideavim
    d.goto("/")
    d.mark("01-home-empty")
    d.hold(2)
    d.scan("JetBrains/ideavim")
    # 0:05 Output identical to the CLI
    d.move(p.locator(".term__cmd").first, dx=0.3, steps=15)
    d.mark("02-ideavim-result")
    d.hold(2.5)
    # 0:08 Filter
    d.click(p.locator("[data-filter]"))
    d.type("commit", delay=90)
    d.mark("03-filter-commit")
    d.hold(2)
    d.clear_field()
    # 0:11 Second repo via "/"
    d.scan("JetBrains/kotlin", via_slash=True)
    d.mark("04-kotlin-result")
    d.hold(1.5)
    # 0:15 Catalogue → stored ideavim
    d.nav_click(p.locator("a.brand"))
    d.mark("05-catalogue")
    d.hold(2)
    d.nav_click(p.locator("#catalogue a[href*='ideavim']").first, dx=0.2)
    d.mark("06-stored-ideavim")
    d.hold(1.5)
    # 0:20 Similar skills
    d.nav_click(p.locator("pre a[href*='extensions-api-migration']").first, dx=0.3)
    d.move(p.locator("a[href*='/stored?repo='][href*='kotlin']").first)
    d.mark("07-similar")
    d.hold(4)
    # 0:26 Outro
    d.card([
        '<span style="color:#7ee787">$</span> pip install -e .',
        '<span style="color:#7ee787">$</span> skill-atlas serve',
        '<span style="color:#8b949e;font-size:22px">skill-atlas web UI on http://127.0.0.1:8000/</span>',
    ], mark="08-outro")
