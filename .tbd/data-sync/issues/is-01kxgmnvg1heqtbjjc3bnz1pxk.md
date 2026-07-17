---
type: is
id: is-01kxgmnvg1heqtbjjc3bnz1pxk
title: Publish MetaBrowser v0.1.0 to PyPI
kind: task
status: closed
priority: 2
version: 10
spec_path: docs/specs/metabrowser-v0.1.0.md
labels:
  - release
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.385Z
updated_at: 2026-07-17T20:20:35.622Z
closed_at: 2026-07-17T20:20:35.621Z
close_reason: MetaBrowser v0.1.0 was published from exact commit e4df7ac via successful trusted-publishing run 29610357474. GitHub release and PyPI wheel/sdist are public and not yanked; exact kpress==0.2.2 metadata, uvx, global metab/metabrowser CLIs, six built-in plugins, KPress rendering, extension discovery, and the pinned public Agent Skill runner were verified from published artifacts. Post-v0.1 work is retained under mb-08aj.
---
After review and merge, configure trusted publishing, create the v0.1.0 release, verify the published artifact, and confirm installation from PyPI.

## Notes

Release candidate e4df7ac is on main with GitHub Actions run 29600115127 fully green. A temporary local v0.1.0 tag passed the complete make verify gate: 705 tests, audits, exact metabrowser-0.1.0 source/wheel builds, artifact inspection, and installed CLI/plugin smoke checks; the temporary tag was removed. GitHub environment pypi now exists, and draft release v0.1.0 targets e4df7ac. PyPI still returns 404 for metabrowser. Remaining: owner adds the pending PyPI GitHub Actions publisher (project metabrowser, owner jlevy, repo metabrowser, workflow publish.yml, environment pypi), then publish the draft release and verify PyPI/uvx/tool/skill installation.
