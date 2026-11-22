---
type: is
id: is-01m7zxyjbk1fbkqxkc03de40wk
title: Normalize macOS architecture selection before packaging a release
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:49:45.842Z
updated_at: 2026-11-22T21:03:19.348Z
started_at: 2026-11-22T21:03:19.346Z
---
With a trailing space in ARCHES, variant_settings predicts universal and Swift builds one arm64 slice. make-dmg.sh then names the new arm64 image using actual slices, but release.sh still selects the earlier universal name. Normalize architecture tokens once, reject unsupported values, and verify the actual slices and tag identity before consuming the image. Use the tested default arm64 for 0.1.0.
