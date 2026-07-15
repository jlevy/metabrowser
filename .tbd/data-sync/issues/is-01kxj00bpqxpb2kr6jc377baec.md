---
type: is
id: is-01kxj00bpqxpb2kr6jc377baec
title: "PR #1 review A9: disable release workflow caches"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:21.430Z
updated_at: 2026-07-15T06:02:32.564Z
closed_at: 2026-07-15T06:02:32.564Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7e: publish.yml enables uv and npm caches despite the release hardening guidance. Remove release-job caches while preserving frozen verified installs and policy coverage.

## Notes

Publishing explicitly disables uv and npm caches while retaining locked installs and audits. Package policy and full gate pass.
