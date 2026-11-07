---
type: is
id: is-01m6tkevv05t0gr8fc59ehyt9b
title: Unify commit and PR description surface styling
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:54:31.519Z
updated_at: 2026-11-07T09:11:32.196Z
started_at: 2026-11-07T08:56:39.004Z
---
User reports some commit description boxes have a gray/code-like background instead of the PR design. Apply the shared description surface treatment: subtle box, normal text color and sans-serif typography. Keep layout and design consistent across commit pages, PR pages and file rendering, reusing existing design tokens/primitives and their shared headers/gutters/reading widths. Preserve actual code and diffs as code, scoped typography, Markdown structure and narrow-screen behavior. Review the common components and update design documentation, focused existing checks and browser evidence before a stacked follow-up.

## Notes

Integrated donor1d5f116d by forward merge. Independent review and94focused checks pass. Real commit0487921d browser confirms neutral page-card/regulartext15px sans22.5px lineheight, authored newlines, shared687px readingcard andx323.99 paneedge matching PRcard. Source/diff spacing untouched. Updated design/e2e/changelog; final combined gate, PR/CI and installation pending.
