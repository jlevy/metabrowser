---
type: is
id: is-01m2fcz9hrj17z9qvbaetmr4br
title: "PR #118 review R2: tree row box exemptions depend on source order"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:43.767Z
updated_at: 2026-09-14T07:26:43.767Z
---
PR #118 review R2 (Medium). styles.css:2353-2360: exemption selectors have equal specificity to the text rule and win only by order; moving them above drops skeletons 1.1px and tests/test_design_vocabulary.py:88-93 still passes. Remove the order dependency and make the test fail if the exemption stops applying.
