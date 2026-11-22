---
type: is
id: is-01m7zxyjbk1fbkqxkc03de40wk
title: Normalize macOS architecture selection before packaging a release
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:49:45.842Z
updated_at: 2026-11-22T21:30:10.225Z
started_at: 2026-11-22T21:03:19.346Z
---
With a trailing space in ARCHES, variant_settings predicts universal and Swift builds one arm64 slice. make-dmg.sh then names the new arm64 image using actual slices, but release.sh still selects the earlier universal name. Normalize architecture tokens once, reject unsupported values, and verify the actual slices and tag identity before consuming the image. Use the tested default arm64 for 0.1.0.

## Notes

2026-11-22: fix in PR #702 (https://github.com/jlevy/metabrowser/pull/702), branch claude/macos-arch-normalize, not merged. normalize_arches in apps/macos/scripts/common.sh is the one reader of ARCHES and of lipo's output (trim, dedupe, canonical order, refuse unsupported or empty); default_arches stays arm64. build-app.sh and release.sh require the built slices to be the ones asked for; release.sh removes an earlier image under the predicted name, passes that name to make-dmg.sh, and has check-dmg.sh check slices and image name (EXPECTED_ARCHES) plus version and commit for a release variant built from a commit. Evidence: scripts/test-release-logic.sh and test-scripts.sh pass on a Mac; the new cases fail on the old scripts; ARCHES='arm64 ' make macos-dmg built and checked the arm64 image. Not run locally: make verify, Swift tests, a release rehearsal, a universal or signed build. Leave open until the PR merges.
