---
type: is
id: is-01m3tjd3zk6s2xbfvqee6h0t2m
title: "Back to a /commit/ URL after an in-page file open leaves the file showing: the Git panel does not restore a commit on a history landing"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T01:49:00.246Z
updated_at: 2026-10-01T01:49:00.246Z
---
Found while building View file (PR #248, mb-zb5t): opening a file in-page from a commit diff and pressing Back lands on the /commit/ URL but leaves the file view showing, because the Git panel does not restore a commit on a history landing (popstate). Predates #248, which works around it with a document load for its link. Also seen in passing: /commit/<abbreviated oid> on a pin shows 'Could not load this commit.' (related to mb-4kuc). Acceptance: a browserless navigation session where Back/Forward across file and commit entries restores each view; an abbreviated OID either resolves or shows a typed state.
