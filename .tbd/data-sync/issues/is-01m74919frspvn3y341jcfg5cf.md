---
type: is
id: is-01m74919frspvn3y341jcfg5cf
title: "App icon: an MB mark in the sister app's style"
kind: feature
status: in_progress
priority: 1
version: 6
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
updated_at: 2026-11-11T07:01:15.213Z
started_at: 2026-11-11T03:18:43.016Z
---
Phase 1. A full, modern icon matching the sister app's Figma-designed v6 icon: its squircle, rim bevel, panel sheen, and inset letter shadows, copied from its SVG masters. The mark is a hand-drawn half-M (|\/) followed by a clean B whose stem completes the M, built on Reddit Mono Bold's construction, in light shades of Metabrowser's JavaScript yellow-green and Markdown purple. Release and canary variants, SVG masters, every icns size, a reproducible build script, and inline review with the user.

## Notes

Draft on branch claude/macos-app-icon (94f75be6, then aecdc4b1; not pushed); awaiting user review of the review renders.
- Masters: apps/macos/AppIcon/metabrowser-icon.svg (release) and metabrowser-icon-dev.svg (dev, canary gold rim), from the sister app's v6 Figma SVG exports; border drawn under the panel instead of masked.
- Glyphs: partial M (|\/) + Reddit Mono Bold B, junction "gap" (vertical face at the mirrored first-stem edge, 21.437 gap = sister app's tip-to-stem distance). "touch" and "overlap" stay available in make-glyphs. The |\ reading was dropped by the user.
- Fills: citrine #ECC44B and amethyst #C896FF (gem tones of the JS and Markdown hues; sister app's relative chroma, 0.06 below its lightness). Alternatives in review/color-comparison-1024.png.
- Build: apps/macos/scripts/build-icon.sh (byte-identical output); review images with --review [--sister SVG] into apps/macos/AppIcon/review/ (gitignored).
- Pending after feedback: small-size masters (16/32), deleting scripts/generate-icon.swift once build-app.sh copies the .icns files.
- Folder is AppIcon/, not Icon/: the user's global gitignore ignores any path named Icon.
