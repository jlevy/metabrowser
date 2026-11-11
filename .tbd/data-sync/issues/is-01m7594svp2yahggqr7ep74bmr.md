---
type: is
id: is-01m7594svp2yahggqr7ep74bmr
title: "PR #348 E5: same-source bind forgets the catalog identity, so a new catalog reader is ignored"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7594pkfe0xdkwhjqrwwpxz2
hold: null
hold_until: null
created_at: 2026-11-11T12:25:54.805Z
updated_at: 2026-11-11T14:23:38.192Z
started_at: 2026-11-11T12:25:55.402Z
closed_at: 2026-11-11T14:23:38.191Z
close_reason: "Fixed: f9f7b9c3. A same-source bind keeps core_catalog_identity with the reader; another source clears both. Test: test_a_catalog_from_another_account_changes_the_reader_after_a_bind (fails with the identity cleared)."
resolution: null
duplicate_of: null
---
Low. served_pull.py:586-592, 605-609. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040
