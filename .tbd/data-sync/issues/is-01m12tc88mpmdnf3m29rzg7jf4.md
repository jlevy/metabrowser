---
type: is
id: is-01m12tc88mpmdnf3m29rzg7jf4
title: Add a check that fails on new visible loading text
kind: chore
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:10.481Z
updated_at: 2026-08-28T00:11:20.046Z
closed_at: 2026-08-28T00:11:20.045Z
close_reason: "Fixed in 101b4ad: tests/test_loading_states.py scans static and builtin_plugins, skipping sr-only spans, aria-labels, the DOM-assigned sr-only idiom, and comments. Allowlist is empty. Verified it fails on a reintroduced message."
resolution: null
duplicate_of: null
---
The repository prefers a check to a sentence. Add a test that scans static and builtin_plugins for visible loading strings and fails on new ones, allowing text inside .sr-only spans and aria-label attributes. Without it the policy is prose that the next feature quietly violates, which is how the Git panel case arrived.
