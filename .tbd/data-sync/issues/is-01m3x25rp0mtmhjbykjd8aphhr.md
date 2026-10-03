---
type: is
id: is-01m3x25rp0mtmhjbykjd8aphhr
title: A mirror's long repository name is cut with an ellipsis while the 'mirror in' note beside it still shows
kind: bug
status: in_progress
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-02T01:03:05.405Z
updated_at: 2026-10-03T05:20:08.587Z
started_at: 2026-10-03T05:05:52.101Z
---
Found 2026-10-01 while running the new step 2 of 5.3 in docs/qa-v012-repository-library.md (PR #263's file-header note) on the stack's tip 25540fa2, in stock Chrome 152.0.7977.83, headless, over the DevTools protocol.

Observed. On a served mirror's file page, the repository's name at the start of the main heading is drawn with an ellipsis while the `mirror in <location>` note beside it is still shown: `metabrowser-v012-landing-d… / README.md   mirror in /private/tmp/…`. The runbook's step (text from #263) says the note disappears whole before the name or any part of the path narrows, and #263's body says the root's name measures exactly what it does with the note removed at thirteen widths.

Measured (un-rounded `getBoundingClientRect`, name `metabrowser-v012-landing-docs`, 186.359 px of text, served from `file://`):
- With the note removed, the name's box is 186.359 px at every window width from 800 to 1700 px.
- With the note present and cut (it needs 1354 px with a scratch home outside the home directory; 703 px for `~/.metabrowser/…`): the box is 186.344 px (1/64 px short) at 1300 to 1700 px and 186.328 px (2/64 px short) at 800 to 1100 px.
- At 2/64 px short Chrome draws the name's last characters as an ellipsis (screenshot at a 1100 px window: `…landing-d…`, note 353 px wide). At 1/64 px short it draws the name whole (screenshot at 1300 px, and a mirror named `metabrowser`, 76.672 px, at 860 px).
- A short name is not affected: `squares` (44.984 px) is whole at every width at which the note shows.

Cause (inferred from the stylesheet, not proven by a fix): `.file-header-root` has `flex: 0 20000 auto` and `.file-header-mirror` `flex: 0 100000000 auto` (static/styles.css), so when the note's text does not fit, the name still takes a share of the shrink in proportion to its width. The share is a fraction of a layout unit for a short name and reaches two layout units for a long one, and `text-overflow: ellipsis` on the name then fires.

When a reader sees it, by the arithmetic above (negative space times the name's width at or above about 82,000 px² for a 703 px note): a repository name of roughly 24 characters or more, with the location under `~`, in a window whose main heading is narrower than about 690 px, while the note is still at least its 168 px minimum. With a `METABROWSER_HOME` whose path is long, at wider windows too.

Not a regular-folder change: a folder's page has no note. Paint only; nothing in the DOM or any route is wrong.

Fix direction (no code was changed): give the note all of the shrink until it is gone (for example `flex-shrink: 0` on the name while the note is in its row, or a container query), and measure un-rounded widths, or compare a screenshot, in whatever holds the layout.

The runbook's 5.3 step 2 names this as a known defect.

## Notes

Candidate fix: mirror note flex basis zero and grow only into remaining space. In-app browser measurement at 12 heading widths from 250 to 1350px: before root lost up to 0.0390625px with the note present; after root equals note-removed baseline exactly at every width. Updated stylesheet assertion. Full gate and delivery pending.
