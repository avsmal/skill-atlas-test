# Web UI demo — video script

A ~3-minute screen recording of `skill-atlas serve` for developers who haven't seen it.
Lead repository: **JetBrains/ideavim**; JetBrains/kotlin and avsmal/skill-atlas-test fill the
catalogue and give cross-repository *Similar skills* hits.

Values below come from a dry run on 2026-09-30 (ideavim `7bd8f1315c8a`, kotlin `d3c2339829f4`,
skill-atlas-test `2599d58c5d2a`). Repositories change: re-run the dry run before recording and
update the numbers (see *Fallbacks*).

## Setup

```bash
pip install -e .
skill-atlas serve --db /tmp/demo.db --port 8000   # fresh DB → empty catalogue
```

- Delete `/tmp/demo.db` before each take so the catalogue starts empty.
- Browser: 1280×800 window, zoom 125 %, dark system theme, no other tabs, bookmarks bar hidden.
- Have a terminal ready for the outro, with the same font size.
- Each scan takes 2–5 s. Record it live; trim the wait in editing if needed.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| **1. Hook** 0:00–0:15 | Home page at `http://127.0.0.1:8000/`. Empty catalogue: *No repositories yet*. Cursor rests on the input (it is already focused). | "Agent skills — the `SKILL.md` files under `.claude/skills` and `.agents/skills` — are how teams teach coding agents their project's conventions. But which skills does a repository actually ship? skill-atlas answers that. One field, one button." |
| **2. First scan** 0:15–0:50 | Type `JetBrains/ideavim`, press Enter. Button shows *Scanning…*, then the output panel: `https://github.com/JetBrains/ideavim @ 7bd8f1315c8a`, six skills (`changelog`, `doc-sync`, `extensions-api-migration`, `git-workflow`, `issues-deduplication`, `tests-maintenance`), `6 skill(s) found`. Hover the title bar `$ skill-atlas scan JetBrains/ideavim`, click **Copy**. | "Let's try IdeaVim. `owner/name` is enough. skill-atlas does a shallow checkout of just the skill folders and lists every skill at the current commit — six of them: changelog, doc sync, a migration helper for the extensions API, git workflow, issue deduplication, test maintenance. The title bar shows the equivalent CLI command: this panel is exactly what the CLI prints, colors included. Copy grabs it as plain text." |
| **3. Links** 0:50–1:10 | Click the path `.claude/skills/git-workflow/SKILL.md` → GitHub opens in a new tab at `…/blob/7bd8f13…/.claude/skills/git-workflow/SKILL.md`. Close the tab. Point at the address bar: `/?repo=JetBrains%2Fideavim`. | "Every path links to the file on GitHub, pinned to the scanned commit, so the link never drifts. And the page itself is a plain URL — share it and your teammate sees the same scan." |
| **4. Filter** 1:10–1:30 | Click *Filter skills…*, type `commit` → only `changelog` and `git-workflow` stay. Replace with `test` → only `tests-maintenance`. Clear the field. | "Big repositories can have dozens of skills. The filter matches names and descriptions as you type — 'commit' finds the changelog and git-workflow skills; 'test' finds test maintenance. It runs in the browser, no round-trip." |
| **5. More repos** 1:30–1:50 | Press `/` (focuses the input and selects its text), type `JetBrains/kotlin`, Enter → 6 skills. Press `/` again, type `https://github.com/avsmal/skill-atlas-test`, Enter → 1 skill (`shared-memory`). | "Slash jumps to the input from anywhere. Let's add the Kotlin compiler — six skills, mostly build tooling — and a full GitHub URL works too: our own repo, with one skill." |
| **6. Catalogue** 1:50–2:15 | Click **skill-atlas** (or *Catalogue 3*) in the top bar. Catalogue: `3 repositories · 13 skills`; rows for skill-atlas-test (1 skill), kotlin (6), ideavim (6) with short commit and scan time. Click **JetBrains/ideavim** → stored page: *6 skills*, commit, *View on GitHub*, **Rescan**, panel titled `$ skill-atlas list --repo https://github.com/JetBrains/ideavim`. | "Every scan is saved to a local SQLite database, and the home page becomes a catalogue: newest first, with skill counts, commits and scan times. Opening a repository reads from the database — instant, no clone, and it works offline. Rescan when you want the latest commit." |
| **7. Similar skills** 2:15–2:40 | Click the skill name **extensions-api-migration** → *Similar to extensions-api-migration*. Top result: `analysis-api-create-cherry-pick-issue` — **18.8 %** — JetBrains/kotlin; below it `tests-maintenance` 17.3 %, `analysis-api-mark-internal-apis` 17.0 %, … `minimize-repro-for-diagnostic-test` 14.0 %. Click the *JetBrains/kotlin* label → Kotlin's stored page. | "Skill names link to similar skills across every repository in the catalogue, ranked by how close their descriptions and bodies are. The closest match to IdeaVim's migration skill lives in the Kotlin repo. That's how you spot overlap — two teams writing the same skill twice — or find a good one to borrow." |
| **8. Outro** 2:40–3:00 | Switch the OS to light theme (page follows); narrow the window to phone width (panel scrolls sideways). Cut to terminal: `pip install -e .` then `skill-atlas serve`. | "Light and dark themes follow your system, and it works on a phone. No dependencies beyond Python, nothing loaded from the internet. `pip install`, `skill-atlas serve`, and point it at your repositories." |

## Fallbacks

- **Numbers changed** (new commit, skills added/removed): update the counts, the filter keywords and
  the percentages. Keep `extensions-api-migration` for scene 7 if its top hit is still in another
  repository; otherwise pick any ideavim skill whose first result is from JetBrains/kotlin. To list
  them all:

  ```bash
  python - /tmp/demo.db <<'EOF'
  import sys
  from skill_atlas.store import Store
  from skill_atlas.similarity import find_similar
  skills = Store(sys.argv[1]).list()
  for t in (s for s in skills if s.repo.endswith("/ideavim")):
      print(t.name, [(k.repo.split("/")[-1], k.name, f"{sc:.1%}") for k, sc in find_similar(t, skills)][:3])
  EOF
  ```

- **Slow network**: cut the *Scanning…* frames in editing. A scan always clones afresh, so
  pre-scanning doesn't make it faster.
- **Rescanning reorders the catalogue** (most recent first) — do scene 6 right after scene 5.
