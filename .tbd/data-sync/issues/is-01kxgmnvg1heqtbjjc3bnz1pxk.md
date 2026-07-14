---
type: is
id: is-01kxgmnvg1heqtbjjc3bnz1pxk
title: Publish MetaBrowser v0.1.0 to PyPI
kind: task
status: open
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels:
  - release
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.385Z
updated_at: 2026-07-14T20:42:54.803Z
---
After review and merge, configure trusted publishing, create the v0.1.0 release, verify the published artifact, and confirm installation from PyPI.

## Notes

Release order: review and merge jlevy/kpress PR #17, publish the resulting KPress patch, update MetaBrowser's exact KPress pin, rerun make verify and GitHub CI, then tag and publish MetaBrowser v0.1.0.
