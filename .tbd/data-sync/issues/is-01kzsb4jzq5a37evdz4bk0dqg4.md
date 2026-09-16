---
type: is
id: is-01kzsb4jzq5a37evdz4bk0dqg4
title: "Repository library Phase 1A: f01 and SoftSchema format foundation"
kind: task
status: in_progress
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m1389aetecehg10qdf7zb9rz
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-11T21:19:58.966Z
updated_at: 2026-09-16T21:10:44.798Z
started_at: 2026-09-16T21:10:44.798Z
extensions:
  linear:
    id: 72de9d89-2da1-484f-b3bf-1a9e3204a9bb
    linked_at: 2026-08-16T08:05:43.426Z
---
Implement METABROWSER_HOME, permissive user config, enforced f01 layout/identity/state records, future-format refusal, migrations, packaged SoftSchema schemas, and atomic YAML. Depend on mb-xa0p for owner-only 0700/0600 or equivalent ACL storage and freeze the home-only-for-layout/global-sweep, entry, then provider/resource lock order with no lock across network work. Select and review the exact first-party SoftSchema release under the owner-confirmed jlevy cool-off exemption, still recording predecessor, lock delta, dependencies, artifact hashes, and runtime reach. Include quarantine, recoverable trash, reclamation, drift/corpus/distribution checks; do not clone or serve.
