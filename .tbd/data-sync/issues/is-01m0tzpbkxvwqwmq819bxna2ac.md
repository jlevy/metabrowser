---
type: is
id: is-01m0tzpbkxvwqwmq819bxna2ac
title: "PR #76 review R8: syntax helper can hang for callers arriving after the optional-asset chain settles"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0tznss30senrnyn9x48gedp
created_at: 2026-08-24T22:54:09.021Z
updated_at: 2026-08-24T23:01:43.873Z
closed_at: 2026-08-24T23:01:43.873Z
close_reason: "Fixed: replaced the incorrect 'settles every waiter' claim with the real readiness rule (check for a loaded grammar first, subscribe only when absent, latch chain completion in the shell, resolve null once the chain finished without the grammar). Added the server.py latch to the surface table, an already-settled-chain case to Phase 1, and the late-caller assertion to the progressive-enhancement tests."
resolution: null
duplicate_of: null
---
Verification of the R1 fix in 5604e04. The plan (Host syntax service) claims 'the optional chain fires metabrowser:optional-assets-loaded after both success and failure, which settles every waiter.' No latch exists: server.py's inline chain dispatches the terminal event once (server.py:1118) and nothing records that it completed; asset-loader.js has no flag either. A helper that only awaits the event never settles when it is called after the event already fired — the normal case for a diff opened seconds after load when highlight.js failed. Specify: resolve immediately when hljs is present, and latch chain completion so a late caller resolves null.
