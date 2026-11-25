---
type: is
id: is-01m87zs7wmwcmah3snhf1yjrnf
title: "Expand between hunks: @@ -a,b +c,d @@ separators open the hidden lines like a fold"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-24T23:55:43.881Z
updated_at: 2026-11-25T08:53:31.515Z
started_at: 2026-11-25T06:22:07.713Z
---
User request 2026-11-24: the hunk separators in the source diff (@@ ranges) should be expandable, fetching the unchanged lines between hunks (and before the first and after the last), in the same fold design as the other collapsible chunks (see the fold-design bead). Needs the lines from the snapshot through a route reachable from metab --api with a golden (parity), fetched on demand, bounded by measured size.

## Notes

PR #830 (https://github.com/jlevy/metabrowser/pull/830), base main, head b8ab5cd19; CI green at that head (run 45579281883). Not merged.

Done: the comparison route's view=lines (sidekick.py, side_lines.py, git.py side_bytes and converts), DIFF_GAP_LINES = 1000 measured in Chrome beside the constant, the gap bars through foldExpander in diff-view.js with place-keeping, highlighting within the syntax budget, failure and refusal copy; route tests and golden, a pull request's answer in cli-github-pull, the browserless session and golden (diff.hunk-gap), the Chrome test (diff.hunk-gap-paint), docs, changelog fragment, and a guided review.

Deferred: Unfold on Docs does not open gaps; a guided review step draws a code file's hunks with plain bars, as a patch file does; Current skips the gaps of a hunk that only deletes; working-tree and index sources answer no_content until they can read their sides; each gap is highlighted on its own (the per-hunk lexer reset on mb-hhmb). When the fold icon change (mb-1gtk) lands, tests/dom/diff-hunk-gap-chrome.mjs reads the .diff-fold-chevron span it removes and needs updating.
