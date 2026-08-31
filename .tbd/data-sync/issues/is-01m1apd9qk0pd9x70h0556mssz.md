---
type: is
id: is-01m1apd9qk0pd9x70h0556mssz
title: "PR #89 F2: local clone defaults to --local, falsifying the decision's rationale"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1apd8ye0cvejxessb3ppzjy
created_at: 2026-08-31T01:19:45.906Z
updated_at: 2026-08-31T01:19:45.906Z
---
Verified on git 2.50.1: a path-form 'git clone <dir>' hardlinks objects (link count 2 on both origin and clone, so the clone is not isolated from source mutation) and git warns '--filter is ignored in local clones; use file:// instead', which breaks blobless acquisition. The file:// form uses the git-aware transport and produces a pack. So 'strictly safer than HTTPS/SSH' and 'goldens on exactly the production code path' are both false for the path form. The decision must pin file:// (or --no-local) rather than accept a bare local path, and must say how a bare path avoids colliding with 'metab <dir>'.
