---
type: is
id: is-01m0jt2k69dmdb6k99nkh4yw4g
title: "R3: two accessors for _rollup_generation with different locking"
kind: task
status: closed
priority: 2
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0jt1hr4r6yqhgxkv0bpyayj
created_at: 2026-08-21T18:42:03.080Z
updated_at: 2026-08-21T19:03:44.407Z
closed_at: 2026-08-21T19:03:44.406Z
close_reason: Kept main's locked rollup_revision() and dropped rollup_generation(). The lock is held for one attribute read on the request path.
---
PR #60 review finding R3 (medium).

rollup_generation() (unlocked, added by #60) and rollup_revision() (locked, on main from
#59) both return self._rollup_generation. Git conflicts on them, so this gets noticed; the
question is which survives.

#60's docstring argues the unlocked read is safe because "the worst a torn read can do is
recompute". True in effect -- and in CPython an int attribute read cannot tear at all, so
the risk being guarded against does not exist. The lock is not buying correctness here
either; it is on the request path and held only for the read.

Keep one accessor. Either is defensible; what is not defensible is shipping both, since a
later reader has to work out whether the difference is meaningful.
