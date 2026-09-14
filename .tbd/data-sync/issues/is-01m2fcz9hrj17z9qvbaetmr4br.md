---
type: is
id: is-01m2fcz9hrj17z9qvbaetmr4br
title: "PR #118 review R2: tree row box exemptions depend on source order"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:43.767Z
updated_at: 2026-09-14T07:58:39.799Z
closed_at: 2026-09-14T07:58:39.798Z
close_reason: "Fixed in 0f399e54 (https://github.com/jlevy/metabrowser/pull/118): box states excluded inside the opt-in selectors with :not(), no order-dependent align-self: center rules; test fails if an exclusion moves or is deleted."
resolution: null
duplicate_of: null
---
PR #118 review R2 (Medium). styles.css:2353-2360: exemption selectors have equal specificity to the text rule and win only by order; moving them above drops skeletons 1.1px and tests/test_design_vocabulary.py:88-93 still passes. Remove the order dependency and make the test fail if the exemption stops applying.
