---
type: is
id: is-01kxj00ds7qpj6cq14qwky2byb
title: "PR #1 review S2: clarify prerelease install commands"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:23.559Z
updated_at: 2026-07-15T06:02:32.698Z
closed_at: 2026-07-15T06:02:32.698Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Non-blocking review recommendation: until metabrowser 0.1.0 is published, target-state README install commands fail. Add a concise source-checkout path and label published-release commands without weakening the zero-install release onboarding.

## Notes

README clearly distinguishes published uvx/global-tool commands from the source-checkout path while retaining the target v0.1.0 onboarding. Flowmark and executable documentation checks pass.
