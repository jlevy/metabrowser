---
type: is
id: is-01m6f3nf55rm1sjpaagqaph6nr
title: Hold every v0.12 surface to the design system
kind: task
status: in_progress
priority: 1
version: 13
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6f3njzx91ssw9yq9x2smtv5
  - type: blocks
    target: is-01m6f3nj5vpvkbw0m300dcy3jr
  - type: blocks
    target: is-01m6f3nmnmmceb1c0rgwvdg8as
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6f3nfjp6kwy4m46fjjdpfbb
  - is-01m6f3ng0aqr0eq1pbpp5nzf7e
  - is-01m6f3ngds6yf76vnh9qwfzm5k
  - is-01m6f3ngtspxj6q61n1dmv9672
  - is-01m6f3nh8edcavm9h8kfgav2ne
  - is-01m6f3nhp61he288qpjtst9jb1
hold: null
hold_until: null
created_at: 2026-11-02T21:46:51.940Z
updated_at: 2026-11-03T07:24:05.426Z
started_at: 2026-11-02T21:47:06.817Z
---
Running on the branch. Audit of everything added since v0.11.0, with a finding list surface by surface.

## Notes

2026-11-03: done on PR 280: design-system pass and nine checks; the owner's sans rule for messages at 996ea90d (mb-nts1, test_serif_is_only_for_documents). Merged forward to 284 and 283. Closes when the stack merges.


2026-11-03 pause: a follow-up review of 996ea90d (the sans rule) on PR 280 was started and stopped before it verified anything, so it is still owed: check test_serif_is_only_for_documents, both reading fonts and the system font set in Chrome, and any other message surface still in serif.
