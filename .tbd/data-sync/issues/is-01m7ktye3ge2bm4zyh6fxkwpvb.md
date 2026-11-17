---
type: is
id: is-01m7ktye3ge2bm4zyh6fxkwpvb
title: "PR #496 review A3: the stack-integration sketch merges without a Git identity"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:22.576Z
updated_at: 2026-11-17T04:08:31.887Z
closed_at: 2026-11-17T04:08:31.887Z
close_reason: "Fixed in 8b4da0cb: the stack-integration sketch sets git config user.name and user.email before git merge; mb-r283 says so."
resolution: null
duplicate_of: null
---
plan:399-400 against .github/workflows/ci.yml:245-246. Keep git config user.name/user.email before git merge in the sketch.
