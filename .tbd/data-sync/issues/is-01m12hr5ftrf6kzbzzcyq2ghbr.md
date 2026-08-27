---
type: is
id: is-01m12hr5ftrf6kzbzzcyq2ghbr
title: "Git commit summary: revision hash renders larger than sibling metadata text"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-27T21:24:23.673Z
updated_at: 2026-08-27T21:41:14.687Z
closed_at: 2026-08-27T21:41:14.686Z
close_reason: "Fixed in 17ab718: .git-commit-sha steps down to --nav-font-size (13px mono vs 14px sans reads level); design-system doc and contract test updated to record the exception."
resolution: null
duplicate_of: null
---
In the commit page summary (subject, hash, review age, M/A file counts, +/- line counts) the abbreviated hash is styled larger than the other metadata; it should match. CHANGELOG 0.8.0 claimed 'Commit summaries keep the revision at the standard interface size' but the report says it still renders larger. See renderCommitSummary in git-panel.js and .git-commit-* styles.
