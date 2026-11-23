---
type: is
id: is-01m83rbtgd439jbxvbg3v6srkg
title: The store read allowlist admits hash-object -w; refuse writing object commands under the read policies
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-23T08:29:06.444Z
updated_at: 2026-11-23T08:29:06.444Z
---
From review B of #740 (B4): the git store read policies admit 'hash-object -w', which writes an object. No production path passes -w (the one caller is diff/adapters/git.py, fixed arguments), but the allowlist should refuse it under the read policies. tests/test_git_store_read_policy.py:59 uses it on purpose and needs rework.
