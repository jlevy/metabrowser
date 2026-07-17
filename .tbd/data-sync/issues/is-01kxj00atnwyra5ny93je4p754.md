---
type: is
id: is-01kxj00atnwyra5ny93je4p754
title: "PR #1 review A5: freeze every uv execution path"
kind: bug
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:20.532Z
updated_at: 2026-07-17T21:16:36.943Z
closed_at: 2026-07-15T06:02:32.347Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level review finding 5 and fresh review R2: direct documented uv commands and CI/publish/Make/hook uv execution could merge machine-global config or re-resolve a stale lock. Pin repository config for direct mutating/resolution commands, use frozen/no-sync execution consistently, align locked-install documentation, and enforce the policy.

## Notes

Make, hooks, workflows, and executable docs use frozen uv execution; direct dependency commands pin uv.toml; package policy rejects bare documented add/lock/sync commands. Nine focused policy tests and full gate pass.
