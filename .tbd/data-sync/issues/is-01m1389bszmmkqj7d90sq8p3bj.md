---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-08-31T01:21:06.091Z
---
Revised 2026-08-30 after the PR #89 review (finding F2).

cache/urls.py classifies transport as https, ssh, or file, and accepts file:// URLs as Git sources. acquire binds a file source to the untrusted profile unconditionally. A bare local path is NOT a Git source: `metab /path/to/repo` keeps meaning "serve that directory", so the grammar has no ambiguity to resolve and acquisition must be asked for explicitly.

The first draft accepted bare paths, justified as "strictly safer" than HTTPS/SSH. That was wrong. Verified on git 2.50.1: `git clone <path>` defaults to --local, which hardlinks .git/objects into the clone (loose object link count 2 from both sides, so the entry is not isolated from source mutation) and ignores --filter, warning "--filter is ignored in local clones; use file:// instead" — which silently defeats blobless acquisition. file:// uses the git-aware transport, produces a pack, and honours --filter.

Implementation must therefore reject the path form as a Git source and accept only file://, and the acquisition goldens must build file:// origins.
