---
type: is
id: is-01m8857xyfxsj228ngzhzzkavc
title: Lines-changed summaries leave out a zero side
kind: task
status: closed
priority: 3
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/824
    at: 2026-11-25T05:41:37.130Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T01:31:08.094Z
updated_at: 2026-11-25T05:54:39.385Z
started_at: 2026-11-25T01:47:19.075Z
closed_at: 2026-11-25T05:54:39.382Z
close_reason: "Merged in #824 (8fd3362f6): the Pulls tab's rows and stack headings leave out a zero side of their lines (+1,093 alone, −493 alone), show both when both are nonzero, and a muted \"0 lines\" when neither changed."
resolution: null
duplicate_of: null
---
The owner asked (2026-11-24): a lines-changed summary omits +0 and -0. A change that only adds lines reads +1234 in green with no red -0; one that adds and removes always lists both.
