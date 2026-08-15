---
type: is
id: is-01kzz47jbbmcqr2g339n598nd9
title: "PR #35 review R9: TODO checkbox and spec placement contradict the shipped feature"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:43.179Z
updated_at: 2026-08-14T03:32:10.487Z
closed_at: 2026-08-14T03:32:10.486Z
close_reason: "Partly fixed in 78ee53e: TODO.md entry is now checked. Spec deliberately stays in specs/active — plan-2026-08-09-nav-filter-controls.md sets the same precedent, and two other active specs cross-reference this one as a live design contract via sibling-relative links."
---
TODO.md adds the keyboard help entry unchecked while the PR ships it, and the spec is Status: Implemented and validated but stays in docs/project/specs/active/ and in the Active Feature Plans list.
