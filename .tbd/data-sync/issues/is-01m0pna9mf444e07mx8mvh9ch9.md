---
type: is
id: is-01m0pna9mf444e07mx8mvh9ch9
title: Compared a depth-capped tree against the depth=0 one the browser actually uses
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:50.286Z
updated_at: 2026-08-23T06:35:50.286Z
---
WHAT HAPPENED. The equivalence check polled `/api/tree?depth=2` and found seven tally fields populated on v0.6.0 and null on the candidate. Reported as a regression. It is not one: after #66, `depth=0` is the channel that computes tallies, and `depth=2` serves them only from a fresh memo. The browser fetches `depth=0` (app.js:1032). So the check compared a computed answer against one that was never asked to be computed.

WHY IT WAS EXPENSIVE. The finding was specific, reproducible, and wrong, which is the worst combination -- it survived being re-run, because re-running reproduced the same mistake. It was only caught by asking what the client actually requests.

THE GENERAL SHAPE. An equivalence test is only as meaningful as its choice of endpoint. Picking one because it returns more data -- which is why depth=2 was chosen -- picks the endpoint least like the one under test.

THE FIX. The harness should take the endpoint from what the client uses, name that endpoint in its output, and say in its docstring why that one. A comparison that does not record which channel it compared cannot be interpreted later. The real difference at depth>=1 is genuine and deliberate and is tracked separately as mb-amyt; this bead is about the method that mistook it for a regression.
