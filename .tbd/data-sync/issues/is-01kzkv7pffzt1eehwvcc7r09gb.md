---
type: is
id: is-01kzkv7pffzt1eehwvcc7r09gb
title: "PR #22 review R9: revealInTree bypasses escapePathForSelector"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:05:51.470Z
updated_at: 2026-08-09T18:21:04.142Z
closed_at: 2026-08-09T18:21:04.142Z
close_reason: "Fixed in 5f711b8; each has a regression test verified to fail without its fix. make verify green: 783 pytest, 28 golden, both TS configs, hygiene, supply chain, distribution."
---
app.js:3988 and app.js:4003 interpolate raw paths into data-path selectors although the file defines escapePathForSelector() and documents it as used by every dynamic selector. Live repro with a filename containing a double quote: the row appeared, Enter left the palette open, console reported an invalid selector, and neither hash nor preview changed. Fix: escape both current and path, or compare dataset.path directly, then extend test_path_selector_escaping_js.py with end-to-end revealInTree coverage for quotes and backslashes.
