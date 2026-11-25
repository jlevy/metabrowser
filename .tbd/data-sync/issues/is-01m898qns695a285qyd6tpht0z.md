---
type: is
id: is-01m898qns695a285qyd6tpht0z
title: "PR #838 A1: a pending or unpaired step replaces the kept guide with guide changed"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
hold: null
hold_until: null
created_at: 2026-11-25T11:51:24.197Z
updated_at: 2026-11-25T13:15:02.278Z
started_at: 2026-11-25T12:28:26.145Z
closed_at: 2026-11-25T13:15:02.276Z
close_reason: "fixed in ed4b9c780 (PR #838); dispositions: https://github.com/jlevy/metabrowser/pull/838#issuecomment-7163500057"
resolution: null
duplicate_of: null
---
Medium. guided-review.js:176-177 renders updated for any record_revision other than the expected one; the stack route answers not_cached and stack_unavailable with a null record_revision (guided_review.py:1669-1675), so moving to an unread step while the stack is pending empties the outline and disables the arrows. Fix: a null revision is a refusal of that step; a not_cached stack step gets its own words; pin with a session case. Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
