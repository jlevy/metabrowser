---
type: is
id: is-01kzkv7pffzt1eehwvcc7r09gb
title: "PR #22 review R9: revealInTree bypasses escapePathForSelector"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:05:51.470Z
updated_at: 2026-08-09T18:05:51.470Z
---
app.js:3988 and app.js:4003 interpolate raw paths into data-path selectors although the file defines escapePathForSelector() and documents it as used by every dynamic selector. Live repro with a filename containing a double quote: the row appeared, Enter left the palette open, console reported an invalid selector, and neither hash nor preview changed. Fix: escape both current and path, or compare dataset.path directly, then extend test_path_selector_escaping_js.py with end-to-end revealInTree coverage for quotes and backslashes.
