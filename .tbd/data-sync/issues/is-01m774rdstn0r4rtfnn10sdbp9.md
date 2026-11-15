---
type: is
id: is-01m774rdstn0r4rtfnn10sdbp9
title: Pre-mount non-default view tabs at idle
kind: task
status: closed
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:43.801Z
updated_at: 2026-11-15T06:55:40.105Z
closed_at: 2026-11-15T06:55:40.104Z
close_reason: "H105 merged on 2026-11-14 into H112 (mb-wki1), one surface store, per the architecture review (R1): one kept host per subject replaces the separate retention tiers, and H112 records a lettered verdict for this mechanism. Its premise held only for the folder view at final main (exp-079); idle mounting is H112 (d)."
resolution: duplicate
duplicate_of: is-01m7ezshzwvgr17jz8fkawd3hz
---
After the default view settles, mount other views in idle time, bounded by size. Measured as first view-tab visit.

## Notes

2026-11-14: H105's premise holds only for the folder view at final main (exp-079: first Markdown visit 29.5 ms against a revisit at 29.7; JSON 29.4 against 31.3; folder 46.9 against 30.9). Re-scope to the folder view or retire before its round. Its idle-time guard needs a reading the recorder does not take (mb-tpol).
