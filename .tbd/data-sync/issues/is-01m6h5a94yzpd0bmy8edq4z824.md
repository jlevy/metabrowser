---
type: is
id: is-01m6h5a94yzpd0bmy8edq4z824
title: "PR #283 Qodo4457437401: old-Git ancestry verification cost"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:54:11.357Z
updated_at: 2026-11-03T20:17:10.541Z
closed_at: 2026-11-03T20:17:10.541Z
close_reason: Review disposition completed and published, with independent controls supporting the rebuttal or decline. The reviewer-visible threads remain open; this closure records completed triage rather than an unimplemented source fix. Final stack gates passed at ea771741; no PR merged.
resolution: null
duplicate_of: null
---
Medium review https://github.com/jlevy/metabrowser/pull/283#discussion_r4457437401 at04f8b202. Proposed decline of alternates-only verification: a bare full store with no alternates can have a missing ancestor. Existing test_old_git_cannot_hide_a_missing_ancestor_below_its_merge_base deletes one and proves old candidate reduction can hide it. Full ancestry verification under Git<2.45 is intentional correctness work; modern Git keeps pruned path, STORE_READ_POLICY bounds15s and typed timeout preserves record. Existing mb-w8dc measured200k median0.91s vs modern0.021s; mb-hjez records2.8-3.0s under15sbound. No unsupported large-repo timeout reproduction supplied; safe optimization would require a completeness proof rather than alternates absence.

## Notes

Coordinator approved decline of alternates-only optimization: existing bare-origin/no-alternates ancestor-deletion regression passes and demonstrates lost corruption detection if the successful old-Git candidate is pruned.30focused tests include missing ancestor, criss-cross(old/current x shallow/full), typed timeout and record preservation. Existing measured200k old-Git median0.91s versus modern0.021s (mb-w8dc);15s process bound remains. Retain correctness-driven conservative path; no claim unbounded repositories always meet deadline. Declined thread stays open. Root owns publication/sync/closure.
