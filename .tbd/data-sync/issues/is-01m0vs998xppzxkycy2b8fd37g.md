---
type: is
id: is-01m0vs998xppzxkycy2b8fd37g
title: Publish and verify v0.7.1
kind: task
status: closed
priority: 0
version: 3
labels:
  - release:v0.7.1
dependencies: []
parent_id: is-01m0vs8cjjpcz1h53bz34290n5
created_at: 2026-08-25T06:21:23.612Z
updated_at: 2026-08-25T06:57:05.635Z
closed_at: 2026-08-25T06:57:05.622Z
close_reason: Published v0.7.1 from corrected main commit 650dbcd after the documentation-pin gate caught the first attempt before PyPI. Verified GitHub release target, PyPI metadata and AGPL license, wheel and sdist, three public CLI entry points, the public Agent Skill, exact global installation, and the live 8413 commit-diff/menu behavior.
resolution: null
duplicate_of: null
---
Merge the validated patch PR, create the v0.7.1 GitHub release and tag with aggregate notes since v0.7.0, watch trusted publication to PyPI, verify public metadata and distributions, run both documented console-command smoke tests plus the Agent Skill install smoke test, and install the public release globally.
