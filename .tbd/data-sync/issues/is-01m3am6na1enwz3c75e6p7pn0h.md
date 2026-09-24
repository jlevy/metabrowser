---
type: is
id: is-01m3am6na1enwz3c75e6p7pn0h
title: TOC drawer toggle scrolls away with the document in a narrow preview pane
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T21:12:34.879Z
updated_at: 2026-09-24T21:28:19.793Z
started_at: 2026-09-24T21:28:19.789Z
---
Found during the v0.12 alpha acceptance (mb-gnr9) on the integrated stack (PR #241, head aa1f4d93; installed wheel 0.11.1.dev400+250a10c4).

At a pane width where the Contents rail folds into a drawer, the drawer's toggle button (`.kpress-toc-toggle`, `position: fixed`) scrolls away with the document, so the drawer can be opened only from the top of the page. QA runbook 5.9 step 5 (added by #240) expects the toggle to appear after scrolling down.

Cause: `.preview-pane` in `src/metabrowser/static/styles.css` is both the scroll container (`overflow-y: auto`) and, through `transform: translateZ(0)` and `container: kpress-doc / inline-size`, the containing block for fixed descendants. A fixed element whose containing block is itself the scroller is laid out in its scrollable overflow, so it moves with the content. The comment beside the rule says the floating UI should stay pinned to the pane frame. The rule dates from the first standalone package, so the trusted KPress TOC behaves the same; #240's untrusted TOC inherits it.

Reproduction (no network):
1. Serve any Markdown long enough to earn a TOC, trusted (`metab docs/`) or mirrored (`metab 'https://github.com/jlevy/metabrowser/blob/main/docs/development.md'`).
2. Open it at a window width of about 1000 px, so the rail folds away.
3. Scroll the document down. Measured in the browser: the toggle has class `show-toggle` and computed `position: fixed`, yet `getBoundingClientRect().y` is about -8276 px after scrolling 8292 px, so it is off screen. At the top of the document it opens the drawer and the backdrop or an entry closes it.

Acceptance test: a browser-level check (Playwright/real browser, since this is paint and layout) that, at a width where the TOC is a drawer, scrolls the preview pane down and asserts the toggle's bounding box stays inside the pane's visible frame, for both a trusted folder and a served mirror. Keep QA 5.9 step 5 as the manual check.

Owning PR: pre-existing on main (styles.css `.preview-pane`); surfaced by #240's untrusted TOC and its runbook step.
