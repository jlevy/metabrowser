---
type: is
id: is-01m7bbhb96w6ytqrs1tbj69jkr
title: 'Pulls: expanding a PR shows its files or progress, never a "Show N files" offer'
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T21:03:09.605Z
updated_at: 2026-11-13T22:16:15.972Z
closed_at: 2026-11-13T22:16:15.971Z
close_reason: "Merged in #406: an expanded empty Pulls file tree always draws its first rows (an offer only stands in for a change to drawn rows), shows progress until they arrive, and a completed refresh with no rows reads at once without a 1 s error loop. Follow-ups: mb-aw30, mb-5mcn."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "on the PR view, why when I expand a PR did it instead of expanding or showing progress indicator, it had a link \"Show files\"? that should never happen."

Cause, from reading main: `pull-files-tree.js` withholds rows that arrive late behind an offer (`describeFileTree`: "Show N files" when nothing is drawn). The poll comment says late rows wait for the reader, "the first into an empty tree" included; the condition `(rows.length > 0 || !opening) && late()` withholds an empty, non-opening tree.

Rule: expanding a pull request shows its files, or a progress indicator until they arrive (no spinner flash under about 50 ms). An offer may only stand in for a change to rows already drawn, never for the first rows of an empty tree.

Done when: an expanded empty tree always draws its first rows, whenever they arrive; the browserless Pulls session pins a late first answer drawing rows with no offer; and the docs state the rule.
