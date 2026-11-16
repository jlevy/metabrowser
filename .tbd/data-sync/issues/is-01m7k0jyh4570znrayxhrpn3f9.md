---
type: is
id: is-01m7k0jyh4570znrayxhrpn3f9
title: "PR #479 B3: the commit totals line loses its spaces without the diff plugin's stylesheet"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T20:25:43.203Z
updated_at: 2026-11-16T20:25:43.203Z
---
Low. PR #479 review B (https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5926995563). renderCommitTotals (static/git-panel.js:425-428) has no whitespace between file count, dot and change line; spaces come only from builtin_plugins/diff/styles.css:54, :110. Put spaces in the markup; update pins in git-panel-behavior.js and git-commit-summary-chrome.mjs:514.
