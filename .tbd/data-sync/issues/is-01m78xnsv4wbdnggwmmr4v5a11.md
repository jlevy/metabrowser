---
type: is
id: is-01m78xnsv4wbdnggwmmr4v5a11
title: "PR #382 A3: REVEAL_STRIP_MAX_ITEMS is measured but not chosen"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xnek6h8yd4znc1a47kdwm
hold: null
hold_until: null
created_at: 2026-11-12T22:22:26.659Z
updated_at: 2026-11-12T22:40:15.752Z
started_at: 2026-11-12T22:34:59.781Z
closed_at: 2026-11-12T22:40:15.751Z
close_reason: "fixed in e1beb050: REVEAL_STRIP_MAX_ITEMS = 7 (bottom quarter at 180px pane, 100% zoom); 200% zoom recorded as out of the rule's reach. Reply: https://github.com/jlevy/metabrowser/pull/382#issuecomment-6837907014"
resolution: null
duplicate_of: null
---
Severity: Low. PR #382, review A: https://github.com/jlevy/metabrowser/pull/382#pullrequestreview-5882884024. src/metabrowser/static/keyboard-help.js:13-28 and QA check 13 (docs/qa-v012-repository-library.md:941-949) record the Chrome measurements but leave the cap at 8, the most the reveal surface lists, so it bounds nothing. Decided: set 7, the most items that stays within the panel's bottom quarter at the 180px minimum and 100% zoom, and record that no cap meets the rule at 200% zoom (a transient overlay shown only while Shift is held).
