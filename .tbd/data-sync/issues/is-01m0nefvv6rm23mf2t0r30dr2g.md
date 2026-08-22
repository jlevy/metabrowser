---
type: is
id: is-01m0nefvv6rm23mf2t0r30dr2g
title: Replace the prose Scanning… message under File Overview with the standard progress affordance
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:17:18.309Z
updated_at: 2026-08-22T19:17:18.309Z
---
Two problems, reported in QA.

1. It is a prose loading message. builtin_plugins/folder/distribution_view.js:144 sets 'Scanning… percentages cover files indexed so far.' The design system's position is that loading states are a spinner or a filling skeleton box, not a sentence explaining the state. The sibling line at :142, 'Indexing failed; percentages cover files indexed before the failure.', is the same shape and should be reconsidered with it -- though a failure is a stated outcome rather than progress, so it may legitimately stay as text.

2. It appears not to clear. Reported still showing after the scan finished. Needs reproducing against the status handle's update path to find whether the terminal update never arrives or arrives and does not clear the node.

What to build instead: the nav panel already has the right affordance. server.py renders #index-progress with .index-progress-spinner and .index-progress-text, and app.js:2705 fills it with 'Scanning…' or '~N files scanned'. The folder Overview should show that same component -- same markup, same spinner, same '~N files scanned' text, same show/hide triggers -- rather than a second, differently-worded progress language. Confirm it hides on every path the nav one hides on, including index done, index failed, and a folder switched mid-scan.
