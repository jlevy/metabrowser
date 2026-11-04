---
type: is
id: is-01m5wd8dgya8tphw2zjb6dffzk
title: A missing git is reported as an unparseable Git version
kind: bug
status: closed
priority: 3
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-26T15:28:55.837Z
updated_at: 2026-11-04T17:14:29.831Z
started_at: 2026-11-01T16:05:45.631Z
closed_at: 2026-11-04T17:14:29.831Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
On a host with no `git` on PATH at all, asking for a Git source reports the version floor rather than the absence:

    metab https://github.com/owner/repo --no-serve
    Error: unsupported Git version (unparseable); acquisition requires 2.43.7 or a patched release at least 2.50.1 on a newer track

Observed on main (0b016e4b) on 2026-10-26 with an empty environment and a PATH holding no git.

The refusal itself is correct and well behaved: exit 1, no traceback, no local path, and no cache directory created. Only the wording misleads, because it blames the version of a program that is not there. Say that git was not found, and keep the floor sentence for a git that is present but too old.

Low priority: it costs a reader one wrong guess, and it cannot reach anyone browsing a plain folder, which needs no git.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
