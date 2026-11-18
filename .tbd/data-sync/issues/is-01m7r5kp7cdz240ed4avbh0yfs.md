---
type: is
id: is-01m7r5kp7cdz240ed4avbh0yfs
title: "Flake: test_checkout_ref_selector_chrome refuses /api/tree during a revision switch"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T20:29:42.497Z
updated_at: 2026-11-18T20:29:42.497Z
---
Main CI run 44386715486 at a1100bca6 (#560 merge): chrome (3.12, 3/4) and (3.13, 3/4) failed tests/test_checkout_ref_selector_chrome.py::test_a_checkout_switches_between_its_working_tree_and_its_revisions_in_chrome with 'revisionRequests: refused [/api/tree]'; 3.14 and 3.14t shards passed, as did #559's CI and main at eb6e2e62f. Likely a race between the pin guard and a tree request in flight when the revision changes.
