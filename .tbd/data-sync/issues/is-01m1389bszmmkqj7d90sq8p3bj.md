---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-08-31T17:18:07.324Z
---
Revised 2026-08-30 after the PR #89 review (finding F2).

cache/urls.py classifies transport as https, ssh, or file, and accepts file:// URLs as Git sources. acquire binds a file source to the untrusted profile unconditionally. A bare local path is NOT a Git source: `metab /path/to/repo` keeps meaning "serve that directory", so the grammar has no ambiguity to resolve and acquisition must be asked for explicitly.

The first draft accepted bare paths, justified as "strictly safer" than HTTPS/SSH. That was wrong. Verified on git 2.50.1: `git clone <path>` defaults to --local, which hardlinks .git/objects into the clone (loose object link count 2 from both sides, so the entry is not isolated from source mutation) and ignores --filter, warning "--filter is ignored in local clones; use file:// instead" — which silently defeats blobless acquisition. file:// uses the git-aware transport, produces a pack, and honours --filter.

Implementation must therefore reject the path form as a Git source and accept only file://, and the acquisition goldens must build file:// origins.

## Notes

Corrected 2026-08-31 after the adversarial plan review (PLAN-04).

The earlier note claimed file:// "honours --filter". That does not reproduce. Cloning --filter=blob:none from a file:// origin produced a complete clone -- the blob was present -- both with a default origin, which warns "filtering not recognized by server, ignoring", and with uploadpack.allowFilter=true set on it.

What survives: git clone given a bare path defaults to --local, which hardlinks .git/objects (link count 2 from both sides, so the entry is not isolated from source mutation). file:// uses the git-aware transport and produces a pack. That isolation argument is the reason to pin file://, and it stands on its own.

What does not survive: any claim that file:// makes blobless acquisition work. Whether it works at all over file:// is an open measurement the repository-library plan now owns. Nothing in the golden strategy depends on it, since fixture origins are kilobytes.
