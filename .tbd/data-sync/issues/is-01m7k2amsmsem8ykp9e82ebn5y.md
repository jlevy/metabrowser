---
type: is
id: is-01m7k2amsmsem8ykp9e82ebn5y
title: "PR #452 B2: the commit page guide describes the change-stats row that #446 replaced with the Diff summary"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T20:56:08.243Z
updated_at: 2026-11-16T21:14:50.846Z
started_at: 2026-11-16T20:56:15.411Z
closed_at: 2026-11-16T21:14:50.845Z
close_reason: "Fixed in 8adc81dc7 and 53f916188 on PR #452: browsing-history.md's commit summary list gives the Diff summary as its second item; screenshots retaken in mb-k0p3 after mb-26zj. Disposition: https://github.com/jlevy/metabrowser/pull/452#issuecomment-6929558034"
resolution: null
duplicate_of: null
---
Review B (Low), PR #452, https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5927467914. docs/browsing-history.md:45-56 (at ac20c2c) lists the M/A/D change counts as the commit summary's second item and says only multi-file commits open with a Diff summary. Since 0d99e545e the Diff summary replaces the change-stats row on every commit (docs/design-system.md:974-990, static/git-panel.js:458-464). Fix: the second item is the Diff summary; delete :55-56. Screenshots: file a bead (Fix option 'file a bead and say so in the PR body'), because mb-26zj changes both headers.
