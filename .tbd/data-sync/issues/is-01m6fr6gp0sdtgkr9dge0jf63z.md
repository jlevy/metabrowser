---
type: is
id: is-01m6fr6gp0sdtgkr9dge0jf63z
title: "PR #285 B3: the poll after a window load or refresh re-reads every held row"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fr5ndwyynz3p0n04v5nmkt
created_at: 2026-11-03T03:45:42.079Z
updated_at: 2026-11-03T04:45:13.914Z
closed_at: 2026-11-03T04:45:13.913Z
close_reason: "B3 fixed in 6998cc9b: a poll reads the top window; the held range is re-read only for another list file. Reply: https://github.com/jlevy/metabrowser/pull/285#issuecomment-6595667740"
resolution: null
duplicate_of: null
---
Low. pulls-panel.js poll limit after etag reset. Review B https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5746969019

## Notes

B3 fixed in 6998cc9b: a poll reads the top window; the held range is re-read only for another list file. Reply: https://github.com/jlevy/metabrowser/pull/285#issuecomment-6595667740
