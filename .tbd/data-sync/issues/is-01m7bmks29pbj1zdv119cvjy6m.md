---
type: is
id: is-01m7bmks29pbj1zdv119cvjy6m
title: "Storage: each verified private-file open walks every ancestor with ACL reads"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T23:41:46.440Z
updated_at: 2026-11-14T11:23:51.025Z
closed_at: 2026-11-14T11:23:51.024Z
close_reason: "Merged in #422: verified private opens reuse held directory descriptors only after fresh no-follow stat, mount identity (statx mount id / FSOPT_RETURN_REALDEV fsid), owner, mode and empty-ACL checks on every call; fork-safe ownership; walks hold at most two descriptors; catalog and journals share one verification. Follow-up: mb-f38n."
resolution: null
duplicate_of: null
---
Found while investigating mb-yhvu (#412). Each catalog open runs `open_private_file` on the catalog and its 3 journal files, and every one verifies all of home's parent directories and each directory below home, with ACL reads through ctypes. On main one ready core answer did 108 `open_private_file`, 1,655 `_read_acl`, 1,207 `lstat`. Each syscall releases and retakes the GIL, so beside one CPU-bound thread a 20 ms answer took 2.3 s median (max 9.9 s). #412 cut the opens per answer from 19 to 3; the per-open cost remains.

Done when: verified opens of the same private file reuse a verified ancestor chain (cached by identity and invalidated safely), or the verification is otherwise made cheap without weakening the private-path guarantees in SUPPLY-CHAIN-SECURITY and the storage docs; measured before and after, with security review.
