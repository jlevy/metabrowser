---
type: is
id: is-01m894ftrtpp7a721hzn30r7ch
title: "PR #829 B3: an ask taken before the stack became absent keeps the page reading every second"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m894fq5p2chk8wm0qd0vp1yy
hold: null
hold_until: null
created_at: 2026-11-25T10:37:12.854Z
updated_at: 2026-11-25T10:58:42.600Z
started_at: 2026-11-25T10:37:17.153Z
closed_at: 2026-11-25T10:58:42.599Z
close_reason: "Fixed in 3af9f4f (PR #829): asksAfterRead ends an ask on an absent answer; nextDelay ignores waiting asks while absent. Session absent_ask case. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7160421193"
resolution: null
duplicate_of: null
---
Low. PR #829, review B: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6055810869. asksAfterRead ends an ask only when envelope state is not absent (stack-page.js:202), and nextDelay counts an accepted ask as busy (:605). An absent answer carries its members and fetching (pull_stack.py:721). A not_linear stack whose automatic ask was taken and whose fetch ended without moving the member keeps a visible page reading every second. Fix: drop the absent condition; add the session case.
