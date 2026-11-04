---
type: is
id: is-01m6bxr2wp9rfr7aety12fhnb5
title: "Pull-request Markdown has no paragraph or list spacing: paragraphs run together and bullets sit on the card's edge"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-11-01T16:05:42.933Z
updated_at: 2026-11-04T17:14:29.732Z
started_at: 2026-11-01T16:06:24.911Z
closed_at: 2026-11-04T17:14:29.732Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found 2026-11-01 reviewing main c934a0b4 on pallets/click#3866 and jlevy/metabrowser#268. Measured in the browser: .github-pull-markdown p has margin 0 and ul has padding-left 0 with list-style-position outside, so bullets hang outside the text box, because the shell's global reset applies and builtin_plugins/github/styles.css sets neither. The rendered text arrives wrapped as <div><div><p>, so the existing '> :first-child' and '> :last-child' trims reach only the wrapper. Every description and comment is affected. A regular Markdown file on the same server is spaced normally.

## Notes

2026-11-01: fixed in PR #273, open, CI green at its last read. Close when it merges; its required review has not run.
