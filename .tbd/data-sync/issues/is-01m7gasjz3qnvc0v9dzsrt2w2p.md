---
type: is
id: is-01m7gasjz3qnvc0v9dzsrt2w2p
title: Tooltips only when they add information; none on Pulls nav rows
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T19:26:23.202Z
updated_at: 2026-11-15T19:51:10.889Z
started_at: 2026-11-15T19:27:09.431Z
closed_at: 2026-11-15T19:39:25.433Z
close_reason: null
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"Also, one more small item on the nav column the PRs should not have tooltips. It's distracting. Our general principle should be that you don't have a tooltip unless it adds substantive new information."

Done when:
- Pulls nav rows (pull request rows, stack rows, and their parts) show no tooltip.
- docs/design-system.md states the principle once: a control or row gets a tooltip only when the tooltip adds substantive information that is not already visible, such as a glyph-only control's name, an exact time behind a relative age, or the full text of something cut short. A tooltip that repeats visible text is removed.
- The app's other tooltips are audited against that rule (data-tip-text, title, and the shared tip machinery). Each one that only repeats visible text is removed. Each kept one has its reason recorded, and borderline ones are listed for the user rather than decided silently.
- Ideally, a check in tests/test_design_vocabulary.py (or the tip machinery's own tests) keeps a tip from equalling its element's visible text.
- Chrome or browserless checks pin that Pulls rows have no tip. The CHANGELOG says so.

## Notes

Done in bd90edd32 on claude/tooltips-substantive (cut from ebc2e03d1, pushed, no PR). Removed: every tip on Pulls rows and stack rows (state icon name, age exact time, stack place hint, stack row hint, title/meta cut-short tips); changed-files folder tips that only repeat the folder name (Pulls files tree and diff summary); 'Load more of this file' on Load more. Shell guard: app.js tipAddsInformation shows a data-tip-text equal to its element's own text only while cut short. devtools/check_tooltips.py fails a literal tip equal to its element's literal text. Principle stated in docs/design-system.md, 'Tooltips Add Information'. Chrome: tests/dom/github-pulls-stacks-chrome.mjs (no tip on any Pulls row or part), tests/dom/github-pull-header-chrome.mjs (the rule on whole, spaced, cut, glyph anchors). Borderline tips kept and listed for the user in the report: Pulls changed-file rows' tips, 'Show ignored' tips, treemap parent button, merge arrow, html 'Open as full page', source ref toggle, crumbs.

Decisions (the user, 2026-11-15, on the coordinator's picks: "Use your picks"), applied in f354fcb91: (1) Pulls changed-file rows' tips: keep. (2) 'Show ignored' tips, Files and folder rollup: remove. (3) Treemap parent button 'Open X in Treemap': remove. (4) Merge arrow 'wip merges into topic': remove. (5) HTML preview 'Open as full page': keep. (6) Ref selector 'Switch branch or tag': keep. (7) Nested crumbs' full-path tips: removed; a crumb's tip is now its own name, which the shell shows only while the crumb is cut short (flagged to the coordinator). (8) Files tree rows' rich tooltip: trimmed, leaving out a file's size and the total a folder's chip holds, keeping the exact date and a folder's other total; pinned in tests/test_files_tab_chrome.py.
