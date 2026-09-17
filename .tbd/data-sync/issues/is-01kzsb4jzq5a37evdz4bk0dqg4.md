---
type: is
id: is-01kzsb4jzq5a37evdz4bk0dqg4
title: "Repository library Phase 1A: f01 and SoftSchema format foundation"
kind: task
status: in_progress
priority: 1
version: 30
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
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
    target: is-01m2p1ps48qjh1qt3wmk8s63ra
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-11T21:19:58.966Z
updated_at: 2026-09-17T15:00:01.412Z
started_at: 2026-09-16T21:10:44.798Z
extensions:
  linear:
    id: 72de9d89-2da1-484f-b3bf-1a9e3204a9bb
    linked_at: 2026-08-16T08:05:43.426Z
---
Implement METABROWSER_HOME, permissive user config, and enforced f01 records for source aliases and shared repository stores. Package SoftSchema contracts, future-format refusal, migrations, atomic YAML, quarantine, recoverable trash, reclamation, and owner-only storage through mb-xa0p. Freeze home, source-alias, repository-store, then provider/resource lock ordering with no network under lock; provider bindings and provider-repository records remain owned by Hosted Review Phase 0D and provider storage. Reuse the exact first-party SoftSchema release already selected and shipped in Phase 0C.1; do not change that dependency in this phase. Do not acquire or serve content.

## Notes

From mb-xa0p review: (1) the METABROWSER_HOME resolver must add a real test that local browsing (metab <local-dir>) never resolves, validates, or creates the application home, including with a permissive or symlinked METABROWSER_HOME; the earlier placeholder test was removed because nothing read the variable yet. (2) Write records only by atomic replacement: O_CREAT|O_EXCL temporary file through open_private_file, fsync, then rename inside the verified directory; in-place write opens of an existing file that was ever shared are refused.
From mb-ire2 re-audit: (3) implement the application-home runtime probe (cross-process lock exclusion; closing an unrelated descriptor does not release the lock; verify-absent-under-lock publication with a ctypes no-replace rename as defense in depth); a home that fails is refused as unverifiable. (4) Every lease and lock attempt uses its own open() of the lock file, never a shared or duplicated descriptor. (5) A previously shared lock file is replaced only after acquiring the old file's lock non-blocking; otherwise refuse. (6) The repository-store record carries the store configuration snapshot digest. (7) Purge and quarantine move the alias before the store.
