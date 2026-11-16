---
type: is
id: is-01m7hef4yfyhv3m2z691v3t4bd
title: "PR #459 A5: the key-reveal stand-in renders By age on a Git pin"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjfyhee19b9jnbk7nvqfk
hold: null
hold_until: null
created_at: 2026-11-16T05:49:49.901Z
updated_at: 2026-11-16T05:51:15.975Z
started_at: 2026-11-16T05:49:56.792Z
closed_at: 2026-11-16T05:51:15.974Z
close_reason: "Fixed in fbe443a11: stand-in drops By age on a pin; pin record now lists N and T, asserted in tests/test_key_reveal_session.py (fails before)."
resolution: null
duplicate_of: null
---
Low suggestion. tests/dom/key-reveal-session.js:526-531 always rendered By age, while app.js filterGroupOptions (:5203-5209) drops it on a Git revision, so the pin page registered menu.group.a. PR #459, review A: https://github.com/jlevy/metabrowser/pull/459#pullrequestreview-5915454708
