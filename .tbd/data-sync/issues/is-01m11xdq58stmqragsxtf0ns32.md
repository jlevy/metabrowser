---
type: is
id: is-01m11xdq58stmqragsxtf0ns32
title: "PR #31 review R15: research addendum contradicts the plan on GitHub case aliases"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:09.799Z
updated_at: 2026-08-27T15:44:30.574Z
closed_at: 2026-08-27T15:44:30.573Z
close_reason: "Fixed in dbe3206: research addendum now records that normalization reversed direction; GitHub case aliases do not converge and produce two entries."
resolution: null
duplicate_of: null
---
research-2026-08-11-repo-cache-and-git-url-open.md:70-73 says provider-aware normalization makes GitHub case aliases converge; plan:318-330 preserves path case and does not merge entries. Stale claim from the pre-rewrite design (Cursor C3 fix).
