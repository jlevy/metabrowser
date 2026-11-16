---
type: is
id: is-01m7k5kb9na8d335et9yw8ptpz
title: "PR #485 A2: The tag rule is deferred to the runbook, but the CI design already decides it"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:19.156Z
updated_at: 2026-11-16T22:09:53.702Z
started_at: 2026-11-16T21:53:36.512Z
closed_at: 2026-11-16T22:09:53.701Z
close_reason: "Fixed in 83ef69fc3: docs/publishing.md macOS App Releases holds one tag rule (check absent, gh api git/refs at the approved SHA, verify, then gh release create --draft --verify-tag; never a push from a clone); apps/macos/README.md drops git tag -a and git push origin and cites it; Q8 narrowed; mb-mww5 confirms an owner-token tag starts the workflow."
resolution: null
duplicate_of: null
---
Medium. PLAN:321-322, :329, :468-469, :567-568; apps/macos/README.md:425, :478-479; docs/publishing.md:15-18, :27-41. The README creates and pushes a tag from a clone; publishing.md sends tags through gh; a draft does not create its tag. Fix: one rule in docs/publishing.md (gh api git/refs at the approved full SHA, never a push from a clone, then gh release create --draft --verify-tag), cited by the README; narrow Q8; mb-mww5 confirms a tag created with the owner's token starts the workflow. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
