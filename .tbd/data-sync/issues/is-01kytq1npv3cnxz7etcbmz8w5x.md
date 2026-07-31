---
type: is
id: is-01kytq1npv3cnxz7etcbmz8w5x
title: Adopt KPress --kpress-font-size-base once upstream lands (collapse KPress bridge)
kind: chore
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-07-30T23:51:38.970Z
updated_at: 2026-07-31T01:51:45.625Z
---
FONTS — finish after the next kpress release (fixes jlevy/kpress#37).

Precondition: bump kpress pin in pyproject.toml (currently kpress==0.2.2) and commit uv.lock. Respect SUPPLY-CHAIN-SECURITY.md (14-day cool-off).

In src/metabrowser/static/styles.css, find the bridge (search "TEMPORARY SHAPE" / "KPress bridge: the px/rem unit boundary"):

DELETE (pure unit workarounds, superseded by upstream base knob):
- The em restatements of heading sizes (.kpress-prose h1..h6 font-size rules)
- The bullet ::before font-size/top/left override rule
- The key-claims/summary/concepts ::before font-size rule
- The --kpress-bullet-size: 0.8em line

ADD: --kpress-font-size-base: var(--document-body-font-size); (exact knob name per the shipped kpress release)

KEEP (metabrowser DESIGN decisions, not unit workarounds — re-express against the new upstream token names if they changed):
- mono at 0.9x (--kpress-font-size-mono -> --document-mono-font-size; kpress ships 0.82)
- small/smaller/tiny collapsed to --document-small-font-size (0.85x)
- --kpress-caps-label-size -> --label-font-size (CONTENTS matches app labels)
- TOC overrides: text-indent 0, per-level padding from 0.75rem base, CONTENTS title label color/weight/tracking

VERIFY: headless Chrome, render README.md at two forced root font sizes (documentElement.style.fontSize 16px vs 13px): every computed size (p, h1, h2, code, TOC title/entries, bullet ::before size+top) must be identical. Expected: prose 17px, h1 ~28.9, h2 ~22.4, code 15.3, TOC entries ~14.45, CONTENTS/tabs 12.

Update docs/design-system.md (px/rem Unit Boundary section): remove the "temporary adapter" paragraph, describe the base-knob contract. make verify needs node >=24.18 (fnm exec --using=24.18.0; unset NPM_CONFIG_BEFORE and NPM_CONFIG_MINIMUM_RELEASE_AGE if npm errors on the min-release-age conflict).
