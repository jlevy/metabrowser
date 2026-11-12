---
type: is
id: is-01m78tvgcvmgyycpcqvd6cvqne
title: "PR #379 E1: window blur exit is a capture listener, so any key that moves focus ends the reveal"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:07.859Z
updated_at: 2026-11-12T21:45:09.294Z
started_at: 2026-11-12T21:33:34.929Z
closed_at: 2026-11-12T21:45:09.293Z
close_reason: "Fixed in 7df7636d (non-capture window blur listener that acts only when the window is the target), red test in 6fb23e7d (stand-in DOM puts the window on the event path; golden steps for a tree arrow, held J, 2, 1, and a press that moved focus). Headless Chrome 152 repro passes against the fixed files. Reply: https://github.com/jlevy/metabrowser/pull/379#issuecomment-6836774865"
resolution: null
duplicate_of: null
---
High. PR #379, review E (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881900155). static/key-reveal.js:213 and :221 register the window blur listener with capture, so an element blur on a focus move (1, 2, 3, tree and Pulls row keys, X, A) ends the reveal and clears pointerPressed mid-press. The session's fake window never received element focus events (tests/dom/key-reveal-session.js:130-145, tests/dom/key-reveal-dom.js:396-407), so golden steps at cli-ui-key-reveal.tryscript.md:507 and :771 record what Chrome does not show.
