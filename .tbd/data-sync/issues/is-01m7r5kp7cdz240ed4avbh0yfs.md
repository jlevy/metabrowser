---
type: is
id: is-01m7r5kp7cdz240ed4avbh0yfs
title: "Flake: test_checkout_ref_selector_chrome refuses /api/tree during a revision switch"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T20:29:42.497Z
updated_at: 2026-11-18T21:26:58.886Z
started_at: 2026-11-18T20:41:10.835Z
closed_at: 2026-11-18T21:26:58.872Z
close_reason: "Fixed in PR #567 (claude/checkout-chooser-refused-tree, head 023d83dde). Cause: the leaving working-tree page's own root-tally refresh, GET /api/tree?depth=0 from fetchRootSummary (app.js:2049, 500 ms after first rows), was sent after the server switched and before the page unloaded, so SourcePinGuard refused it (409 pin_changed); the leaving page logged the 409 and painted the selector's Reload offer. Fix: source-pin-guard.js createSwitchHold holds a page's guarded requests while its own switch is asked (released if the switch is refused or changes nothing, on a bfcache restore, or after LEAVING_BOUND_MS); source-ref-selector.js starts it before POST /api/source/pin. The Chrome driver now records loader/document, full URL, pin, caller and timing per request and asks for tallies every 10 ms during the switch: 3/3 failures without the fix, CI green with it (all four chrome 3/4 shards ran the test). Confirm after merge."
resolution: null
duplicate_of: null
---
Main CI run 44386715486 at a1100bca6 (#560 merge): chrome (3.12, 3/4) and (3.13, 3/4) failed tests/test_checkout_ref_selector_chrome.py::test_a_checkout_switches_between_its_working_tree_and_its_revisions_in_chrome with 'revisionRequests: refused [/api/tree]'; 3.14 and 3.14t shards passed, as did #559's CI and main at eb6e2e62f. Likely a race between the pin guard and a tree request in flight when the revision changes.
