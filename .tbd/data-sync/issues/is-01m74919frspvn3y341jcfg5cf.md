---
type: is
id: is-01m74919frspvn3y341jcfg5cf
title: "App icon: an MB mark in the sister app's style"
kind: feature
status: in_progress
priority: 1
version: 10
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
updated_at: 2026-11-11T14:44:35.048Z
started_at: 2026-11-11T03:18:43.016Z
---
Phase 1. A full, modern icon matching the sister app's Figma-designed v6 icon: its squircle, rim bevel, panel sheen, and inset letter shadows, copied from its SVG masters. The mark is a hand-drawn half-M (|\/) followed by a clean B whose stem completes the M, built on Reddit Mono Bold's construction, in light shades of Metabrowser's JavaScript yellow-green and Markdown purple. Release and canary variants, SVG masters, every icns size, a reproducible build script, and inline review with the user.

## Notes

Draft on branch claude/macos-app-icon (latest 1a847b97; b-over default at feac5831; not pushed); awaiting user review in the app.
- Masters are generated: apps/macos/AppIcon/metabrowser-icon*.json (parameters) + base-release.svg / base-dev.svg (the sister app's v6 structure, border drawn under the panel) -> metabrowser-icon*.svg, by make-glyphs.swift. Parameters and defaults are documented in AppIcon/README.md.
- Default (release and dev): junction "b-over" (B intact at the M's right-stem position; M's rising diagonal ends at a vertical face 21.437 left of the B's stem, no flat top since the cut lies left of the diagonal's top), fills citrine #ECC44B and amethyst #C896FF. Mark 218 units wide vs the sister app's 222.
- Alternates with parameter files: gap (271 wide), bevel (218; plus a dev bevel), corner-bevel (263, cornerCut 0.5), touch (218), overlap (199). Release .icns for each in AppIcon/review/icns/ (gitignored) via build-icon.sh --review.
- Build: apps/macos/scripts/build-icon.sh (byte-identical output, runs under macOS bash 3.2); review images with --review [--sister SVG].
- Pending after feedback: final junction pick, small-size masters (16/32), deleting scripts/generate-icon.swift once build-app.sh copies the .icns files.
- Folder is AppIcon/, not Icon/: the user's global gitignore ignores any path named Icon.

2026-11-11: Merged into claude/macos-app-spike and pushed to jlevy/metabrowser#341 at 21dae3c3 (not to be merged into main until the user says so).
