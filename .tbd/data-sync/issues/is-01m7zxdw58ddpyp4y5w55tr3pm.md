---
type: is
id: is-01m7zxdw58ddpyp4y5w55tr3pm
title: Require exact macOS release assets and verify both draft digests
kind: bug
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/688
    at: 2026-11-21T20:49:44.007Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:40:38.823Z
updated_at: 2026-11-21T20:49:44.008Z
started_at: 2026-11-21T20:42:50.286Z
---
check-release.sh verifies the expected DMG and checksum, but permits unchecked extra attachments and does not validate the checksum file against GitHub’s asset digest before approval. Require exactly the target release assets and fail closed if either pinned digest or byte comparison fails. Prove with shell fixtures.
