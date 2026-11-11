---
type: is
id: is-01m74919frspvn3y341jcfg5cf
title: "App icon: an MB mark in the sister app's style"
kind: feature
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m74919x10s489egs2q6hfn22
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:04:45.303Z
updated_at: 2026-11-11T07:17:45.283Z
started_at: 2026-11-11T03:18:43.016Z
---
Phase 1. A full, modern icon matching the sister app's Figma-designed v6 icon: its squircle, rim bevel, panel sheen, and inset letter shadows, copied from its SVG masters. The mark is a hand-drawn half-M (|\/) followed by a clean B whose stem completes the M, built on Reddit Mono Bold's construction, in light shades of Metabrowser's JavaScript yellow-green and Markdown purple. Release and canary variants, SVG masters, every icns size, a reproducible build script, and inline review with the user.

## Notes

Draft on branch claude/macos-app-icon (94f75be6, aecdc4b1, aa4d4f72; not pushed); awaiting user review of the review renders.
- Masters are generated: apps/macos/AppIcon/metabrowser-icon*.json (parameters) + base-release.svg / base-dev.svg (the sister app's v6 structure, border drawn under the panel) -> metabrowser-icon*.svg, by make-glyphs.swift. Parameters and defaults are documented in AppIcon/README.md.
- Committed masters: junction "gap" (vertical face at the mirrored first-stem edge, 21.437 gap), fills citrine #ECC44B and amethyst #C896FF. Mark 271 units wide vs the sister app's 222.
- Alternate for review: metabrowser-icon-bevel.json / -dev-bevel.json, junction "bevel" (M diagonal over the B's stem, B beveled parallel, 21.437 channel square to the diagonal, stem wedge above the middle bar trimmed). Mark 218 units wide.
- Build: apps/macos/scripts/build-icon.sh (byte-identical output); review images with --review [--sister SVG] into apps/macos/AppIcon/review/ (gitignored).
- Pending after feedback: pick gap or bevel, small-size masters (16/32), deleting scripts/generate-icon.swift once build-app.sh copies the .icns files.
- Folder is AppIcon/, not Icon/: the user's global gitignore ignores any path named Icon.
