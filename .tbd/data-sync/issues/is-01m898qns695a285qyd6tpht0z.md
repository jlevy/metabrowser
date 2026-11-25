---
type: is
id: is-01m898qns695a285qyd6tpht0z
title: "PR #838 A1: a pending or unpaired step replaces the kept guide with guide changed"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
created_at: 2026-11-25T11:51:24.197Z
updated_at: 2026-11-25T11:51:24.197Z
---
Medium. guided-review.js:176-177 renders updated for any record_revision other than the expected one; the stack route answers not_cached and stack_unavailable with a null record_revision (guided_review.py:1669-1675), so moving to an unread step while the stack is pending empties the outline and disables the arrows. Fix: a null revision is a refusal of that step; a not_cached stack step gets its own words; pin with a session case. Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
