---
type: is
id: is-01m0nvgs0cbpzw0nffxe2w8zzc
title: "PR #66 review F3: prune lag is unsound if negation patterns ever work"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:04:59.659Z
updated_at: 2026-08-22T23:16:35.501Z
closed_at: 2026-08-22T23:16:35.501Z
close_reason: "Fixed: the prune spec now rebuilds eagerly whenever a newly read .gitignore contributes a negation, so the lag's monotonicity argument is enforced rather than assumed. Costs nothing today (the pre-existing prefixing bug means none can exist) and stays sound when that prefixing is fixed. The dependency is named in the comment."
---
ignore_filter.py:138-146,174. The lag's monotonicity argument holds only because no negation can enter all_lines: nested patterns are prefixed as f'{rel_dir}/{stripped}', turning !keep.log into literal 'pkg/!keep.log' rather than '!pkg/keep.log'. That prefixing bug is pre-existing on main and NOT a regression, but this PR makes it load-bearing — the same mangled set now decides whether to descend. Fix: rebuild eagerly whenever an accumulated line starts with '!' (costs nothing today since none can exist), and name the dependency.
