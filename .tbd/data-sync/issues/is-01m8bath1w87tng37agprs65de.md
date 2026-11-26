---
type: is
id: is-01m8bath1w87tng37agprs65de
title: "Rendered diff Markdown: head links fall back to the head on github.com; repository links localized"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bathnhy6pkgn4hmjd87hb1
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
hold: null
hold_until: null
created_at: 2026-11-26T07:06:23.676Z
updated_at: 2026-11-26T08:56:54.759Z
started_at: 2026-11-26T07:19:04.109Z
closed_at: 2026-11-26T08:56:54.759Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/874 (head 2bf458b8, CI green); merges with the epic mb-xdjt.
resolution: null
duplicate_of: null
---
diff-markdown.js: a /view/ head link that is not open (pin is not the head, or changed) becomes github.com/<o>/<r>/blob/<head>/<path> instead of plain text; repository links get localize; external links get the external-link mark.
