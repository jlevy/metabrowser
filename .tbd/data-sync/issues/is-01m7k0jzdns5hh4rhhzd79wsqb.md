---
type: is
id: is-01m7k0jzdns5hh4rhhzd79wsqb
title: "PR #479 B5: 3.8 KB more eager startup script, with no recorded measurement"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T20:25:44.116Z
updated_at: 2026-11-16T20:25:44.116Z
---
Low. PR #479 review B (https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5926995563). gzip -6: static/formatters.js 2,773 -> 5,989 bytes, static/plugin-sdk.js 18,704 -> 19,305. Change line and new part kinds used only from on-demand code. Fix: move changeLine/changeLinePaint/changeSummary into the on-demand changed-files-tree bundle, or trim JSDoc and record the measured growth beside startup_script_transfer_kb.
