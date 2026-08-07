---
type: is
id: is-01kzctrph2jcrdp5v7f91ga2a6
title: "git: commit detail with numstat and path translation"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctrvcdztesz9gabmf7zfsn
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:42:58.977Z
updated_at: 2026-08-07T00:43:03.948Z
---
Add metabrowser/git/detail.py: full message body, --numstat and --name-status merge, rename/copy/binary handling, repo-relative to served-root-relative path translation via the safe-path helpers, outside_root flagging, and the changed-file cap reported as files_truncated.
