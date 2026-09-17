---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-09-17T03:03:54.881Z
---
Treat explicit file:// URLs as first-class Git acquisition sources under the untrusted profile. A bare local path is not a Git source: metab /path/to/repo keeps its existing meaning of serving that directory, while acquisition must be requested with file://. The file transport uses Git-aware packing rather than the hardlinked object store created by the implicit --local path form. Do not claim file:// supports blob filtering: verified Git 2.50.1 origins may ignore --filter even with uploadpack.allowFilter; Phase 0 owns that measurement and the full-clone fallback. Acquisition goldens use small deterministic file:// origins and never depend on partial-clone support.

## Notes

Corrected 2026-08-31 after the adversarial plan review (PLAN-04).

The earlier note claimed file:// "honours --filter". That does not reproduce. Cloning --filter=blob:none from a file:// origin produced a complete clone -- the blob was present -- both with a default origin, which warns "filtering not recognized by server, ignoring", and with uploadpack.allowFilter=true set on it.

What survives: git clone given a bare path defaults to --local, which hardlinks .git/objects (link count 2 from both sides, so the entry is not isolated from source mutation). file:// uses the git-aware transport and produces a pack. That isolation argument is the reason to pin file://, and it stands on its own.

What does not survive: any claim that file:// makes blobless acquisition work. Whether it works at all over file:// is an open measurement the repository-library plan now owns. Nothing in the golden strategy depends on it, since fixture origins are kilobytes.
