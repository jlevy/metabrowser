---
type: is
id: is-01m7m4hg27qk1sgq2mzfypb7dh
title: "Pull request page: one freshness timestamp, on the author line"
kind: feature
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels:
  - ui
  - pulls
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-17T06:54:04.357Z
updated_at: 2026-11-17T07:36:30.691Z
started_at: 2026-11-17T06:54:06.915Z
closed_at: 2026-11-17T07:36:30.690Z
close_reason: Done in jlevy/metabrowser#506 (claude/pulls-row-indent)
resolution: null
duplicate_of: null
---
The pull request view says either "Checked just now · fetched 3 h ago via GitHub CLI" or "Fetched just now via GitHub CLI". Show one timestamp, never two: the one that reflects how fresh the data is (the fetch time; a check that found nothing newer does not make the data newer). Move it onto the author line after a bullet: "jlevy wants to merge 1 commit · Fetched just now via GitHub CLI", with the bullet and the fetched time in gray (muted) and the rest in normal text ink.

## Notes

Follow-up from the user: keep it a small, undistracting indication of how recent the fetch is. The Refresh button goes to the right of the text. Neither the text nor the button may change layout as the text changes (reserve a stable width; no shift).
