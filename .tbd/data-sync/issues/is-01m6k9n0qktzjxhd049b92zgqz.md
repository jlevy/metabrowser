---
type: is
id: is-01m6k9n0qktzjxhd049b92zgqz
title: Correct URL acquisition guidance for reused repository stores
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:48:26.354Z
updated_at: 2026-11-04T17:21:01.551Z
closed_at: 2026-11-04T17:21:01.550Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Fresh postlanding documentation review D1: the pull-request guide unconditionally says that a URL opened inside a checkout without --checkout clones a full mirror. acquire_source returns a healthy published store before lender selection, including a remembered borrowing overlay. Qualify full-clone behavior to a fresh acquisition without an admitted named lender, and state that the current working directory is never inferred as a lender. Keep the remembered-checkout example consistent. Fix in the reviewed documentation follow-up; independently verify against acquire.py and actual merged main before closing.
