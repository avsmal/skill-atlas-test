## What and why

<!-- What was asked, what changed, and why. Link issues or earlier PRs. -->

## Spec

<!-- Sections of spec/ added or changed, or "none" with a reason (e.g. CI or docs only). -->

## Tests

<!-- Integration tests added or changed for each spec case, and how you ran them. -->

## Known issues and fragile parts

<!-- Known issues: what is still broken, limited or left for later, and why.
     Fragile parts: what can break easily (assumptions, platform or environment quirks,
     timing, external services, untested paths) and what would reveal the breakage.
     Write "none known" rather than deleting the section. -->

## Checklist

- [ ] Branch created from `origin/main`, one task per PR
- [ ] `spec/` updated together with the code
- [ ] Integration tests cover every new or changed spec case
- [ ] All tests pass locally (`pytest`)
- [ ] CI is green for the latest commit (`gh pr checks --watch`)
- [ ] Memory file `memory/YYYY-MM-DD_HHMM_<branch>.md` committed to this branch
- [ ] Stale records in `memory/` removed (listed in the memory file)
