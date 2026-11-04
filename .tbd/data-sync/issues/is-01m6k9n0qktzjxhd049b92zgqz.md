---
type: is
id: is-01m6k9n0qktzjxhd049b92zgqz
title: Correct URL acquisition guidance for reused repository stores
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:48:26.354Z
updated_at: 2026-11-04T12:48:26.354Z
---
Fresh postlanding documentation review D1: the pull-request guide unconditionally says that a URL opened inside a checkout without --checkout clones a full mirror. acquire_source returns a healthy published store before lender selection, including a remembered borrowing overlay. Qualify full-clone behavior to a fresh acquisition without an admitted named lender, and state that the current working directory is never inferred as a lender. Keep the remembered-checkout example consistent. Fix in the reviewed documentation follow-up; independently verify against acquire.py and actual merged main before closing.
