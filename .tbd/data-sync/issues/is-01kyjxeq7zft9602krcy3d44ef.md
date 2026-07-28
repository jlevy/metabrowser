---
type: is
id: is-01kyjxeq7zft9602krcy3d44ef
title: Migrate CLI golden tests to tryscript
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-07-27T23:09:42.526Z
updated_at: 2026-07-27T23:36:05.647Z
closed_at: 2026-07-27T23:36:05.647Z
close_reason: CLI goldens migrated to tryscript 0.1.7 (first-party, cool-off satisfied); serve banner scenarios stay in pytest; make golden-update added
---
golden-testing-guidelines say CLI console-output goldens should use tryscript (first-party). Replace the ad hoc .txt pytest harness in tests/test_cli_golden.py with tryscript markdown scenarios; wire into make test/CI per supply-chain policy (exact version, lockfile, release-age check). Blocks merge of PR #14.
