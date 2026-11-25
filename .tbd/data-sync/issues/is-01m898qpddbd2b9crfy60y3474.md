---
type: is
id: is-01m898qpddbd2b9crfy60y3474
title: "PR #838 A2: one Guided Review view mixes answers read at two stack pairs"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
created_at: 2026-11-25T11:51:24.839Z
updated_at: 2026-11-25T11:51:24.839Z
---
Medium. The route reads every step at the current pair (guided_review.py:1670-1723) while the view keys answers by the carrier revision alone (guided-review.js:145, 215-226) and the page draws another pair until the reader takes it; the keep path re-reads in place (stack-page.js:1208-1211). Fix: read the guide at the drawn pair; re-read on keep only while the drawn comparison is current. Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
