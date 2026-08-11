---
type: is
id: is-01kxgmnv21hb6wdegrj4xn8fac
title: Import MetaBrowser into the standalone repository
kind: feature
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels:
  - extraction
dependencies:
  - type: blocks
    target: is-01kxgmnv8fs9qcyahf2wm2s939
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:07.936Z
updated_at: 2026-07-17T21:16:31.890Z
closed_at: 2026-07-14T15:59:46.669Z
close_reason: "Initial standalone import is committed and pushed in PR #1; local make verify and GitHub Actions pass on Python 3.12, 3.13, and 3.14 with clean distribution and installed-wheel validation."
---
Land the package source, tests, public documentation, MIT license, simple-modern-uv project scaffolding, tbd integration, and exact kpress dependency as one reviewable initial pull request.

## Notes

Initial import committed as 8f96f22 and opened for review at https://github.com/jlevy/metabrowser/pull/1. Local make verify passes.
