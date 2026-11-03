---
type: is
id: is-01m6f3neny40jwz0qeanc3avfh
title: Re-run large-PR wall-clock claims on a quiet machine
kind: task
status: open
priority: 2
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T21:46:51.453Z
updated_at: 2026-11-03T06:37:03.415Z
---
The study runs alongside other agents, so its wall-clock claims need a quiet re-run, with the rest of the release's quiet work in mb-cf6y.

## Notes

Include public cases with large files, since file count does not predict the page's cost and hydrated rows do (review of #284, E6): astral-sh/ruff #29817 (1,031 files, the study's own github.com case; 114,609 nodes before E1's fix) and astral-sh/ruff #29121 (1,627 files, +705,301 lines), beside the private 1,183-file case (44k nodes). Measure first line, longest task, Back and the Conversation click on each, in adjacent pairs against signed-out github.com.
