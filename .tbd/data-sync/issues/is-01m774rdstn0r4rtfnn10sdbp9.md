---
type: is
id: is-01m774rdstn0r4rtfnn10sdbp9
title: Pre-mount non-default view tabs at idle
kind: task
status: open
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:43.801Z
updated_at: 2026-11-15T06:36:18.685Z
---
After the default view settles, mount other views in idle time, bounded by size. Measured as first view-tab visit.

## Notes

2026-11-14: H105's premise holds only for the folder view at final main (exp-079: first Markdown visit 29.5 ms against a revisit at 29.7; JSON 29.4 against 31.3; folder 46.9 against 30.9). Re-scope to the folder view or retire before its round. Its idle-time guard needs a reading the recorder does not take (mb-tpol).
