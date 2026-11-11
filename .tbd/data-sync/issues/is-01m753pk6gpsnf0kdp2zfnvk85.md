---
type: is
id: is-01m753pk6gpsnf0kdp2zfnvk85
title: "PR #347 D4: a checkout's metadata write by another reader does not restart the reader history"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m753phnahw8439f040swe73f
created_at: 2026-11-11T10:50:46.351Z
updated_at: 2026-11-11T11:12:18.808Z
closed_at: 2026-11-11T11:12:18.808Z
close_reason: "fixed in e7aae837: writes without a store keep only the writer's reader's pairs; test and docs"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review D round 2 at 48660f96 (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5857531488). References: pull_snapshot_cache.py:6-9, pull_record.py:552-562, arch-repository-sources-and-provider-mirrors.md:731-732.
