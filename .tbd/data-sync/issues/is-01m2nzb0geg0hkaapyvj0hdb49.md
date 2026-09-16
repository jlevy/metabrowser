---
type: is
id: is-01m2nzb0geg0hkaapyvj0hdb49
title: "Immutable Git-tree review: publish revision-source PR"
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:43:08.685Z
updated_at: 2026-09-16T21:27:32.615Z
started_at: 2026-09-16T21:12:28.728Z
---
Independently review GitRevisionSubject, GitTreeSource, GitPath, RepositoryStoreTarget migration across every Git consumer and content route, batch framing/cancellation/large-blob behavior, process-safe maintenance locks and durable reachability refs, plugin capability behavior, and two-process concurrent subjects. Resolve findings, run make verify, and publish one formal GitHub PR with gh stacked on exact green mb-tsdc content-source head. Record exact stack/review/CI evidence. Do not merge.
