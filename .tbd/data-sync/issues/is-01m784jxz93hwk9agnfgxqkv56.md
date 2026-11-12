---
type: is
id: is-01m784jxz93hwk9agnfgxqkv56
title: "Ref state: check the inode-reuse case on a Linux filesystem"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:03:58.184Z
updated_at: 2026-11-12T15:03:58.184Z
---
Deferred from review C (C4) on jlevy/metabrowser#368. Argued, not reproduced: on a Linux filesystem that reuses inode numbers, a ref file replaced within timestamp granularity could keep its fingerprint. Impossible on APFS. Run the check on ext4 first; the candidate fix disables the memo for about 2 s after every ref change, so only adopt it if the case reproduces.
