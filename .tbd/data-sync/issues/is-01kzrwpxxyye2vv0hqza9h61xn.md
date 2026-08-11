---
type: is
id: is-01kzrwpxxyye2vv0hqza9h61xn
title: Isolate Git fixture tests from hook environment
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-11T17:07:51.358Z
updated_at: 2026-08-11T17:08:04.260Z
closed_at: 2026-08-11T17:08:04.259Z
close_reason: Git fixture commands now remove repository-local variables reported by git rev-parse --local-env-vars. The regression test passes both normally and with GIT_DIR/GIT_WORK_TREE inherited from a pre-push hook.
---
The gitignore cross-validation test inherits GIT_DIR and GIT_WORK_TREE from pre-push hooks. Its nested git init then targets the caller repository, causing the test to fail even though make verify passes outside a hook. Clear Git's repository-local environment for commands that operate on the temporary fixture.
