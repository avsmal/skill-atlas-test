"""Scenes for docs/demo.mp4: the ~30 s cut of docs/demo-script.md.

    python .claude/skills/record-demo/scripts/demo_30s.py <out-dir> [--port 8766]
"""
import argparse

from demo_kit import Demo

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--port", type=int, default=8766)
args = ap.parse_args()

with Demo(args.out, port=args.port) as d:
    p = d.page
    # 0:00 Home, then scan ideavim
    d.goto("/")
    d.hold(2)
    d.scan("JetBrains/ideavim")
    # 0:05 Output identical to the CLI
    d.move(p.locator(".term__cmd").first, dx=0.3, steps=15)
    d.hold(2.5)
    # 0:08 Filter
    d.click(p.locator("[data-filter]"))
    d.type("commit", delay=90)
    d.hold(2)
    d.clear_field()
    # 0:11 Second repo via "/"
    d.scan("JetBrains/kotlin", via_slash=True)
    d.hold(1.5)
    # 0:15 Catalogue → stored ideavim
    d.nav_click(p.locator("a.brand"))
    d.hold(2)
    d.nav_click(p.locator("#catalogue a[href*='ideavim']").first, dx=0.2)
    d.hold(1.5)
    # 0:20 Similar skills
    d.nav_click(p.locator("pre a[href*='extensions-api-migration']").first, dx=0.3)
    d.move(p.locator("a[href*='/stored?repo='][href*='kotlin']").first)
    d.hold(4)
    # 0:26 Outro
    d.card([
        '<span style="color:#7ee787">$</span> pip install -e .',
        '<span style="color:#7ee787">$</span> skill-atlas serve',
        '<span style="color:#8b949e;font-size:22px">skill-atlas web UI on http://127.0.0.1:8000/</span>',
    ])
