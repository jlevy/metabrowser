---
type: is
id: is-01m0jt1hr4r6yqhgxkv0bpyayj
title: "Reconcile PR #60 nav filtering with #59's tree and tally work"
kind: task
status: open
priority: 1
version: 6
labels: []
dependencies: []
child_order_hints:
  - is-01m0jt2jfea3xk3q7g7n2pnbq1
  - is-01m0jt2jv9ts6y32me52ep67yt
  - is-01m0jt2k69dmdb6k99nkh4yw4g
  - is-01m0jt3enztskcdvmnkb4pdtyc
  - is-01m0jt3f1hdn6aqt75q7ct5bpn
created_at: 2026-08-21T18:41:28.834Z
updated_at: 2026-08-21T18:42:31.600Z
---
PR #60 (nav tree filtering) branched from de6dff96, before #59 merged as b72f807. The two
touch the same four files, and a trial merge shows the seam is where the risk is, not
either change on its own.

Review posted at
https://github.com/jlevy/metabrowser/pull/60#issuecomment-5373855496

Verdict: the design is right -- filtering is a question about a whole subtree, and the
client cannot answer it while /api/stream is capped at root-depth-2, so resolving it in
/api/tree is the correct layer. What needs settling is the merge.

Trial merge result: two textual conflicts (inventory.py, tree.py) and one silent
auto-merge that doubles the cost of the first request a page makes. Children carry the
individual findings.
