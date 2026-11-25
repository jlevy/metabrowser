---
type: is
id: is-01m88nccj3tsqw8ng6w6hj7d1s
title: Lines summaries outside the Pulls tab still show +0 and −0
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:13:11.311Z
updated_at: 2026-11-25T06:14:02.894Z
started_at: 2026-11-25T06:14:02.893Z
---
Reported by the user after #824 merged: the PR page's summary still reads like '+3,893 −0'. The user's rule (mb-efum) was meant for every lines summary: leave out a side that is zero, show both when both are nonzero, and '0 lines' when neither changed. #824 applied it only to the Pulls tab's rows and stack headings behind an opt-in. Done when every surface that paints the shell's brief change line follows the rule (PR page brief summary, diff header, commit hover card and totals line, changed-files summary, Pulls), the opt-in is gone so it is the one behavior, and goldens pin each surface.
