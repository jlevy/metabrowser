---
type: is
id: is-01m5wd8dgya8tphw2zjb6dffzk
title: A missing git is reported as an unparseable Git version
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-26T15:28:55.837Z
updated_at: 2026-10-26T15:28:55.837Z
---
On a host with no `git` on PATH at all, asking for a Git source reports the version floor rather than the absence:

    metab https://github.com/owner/repo --no-serve
    Error: unsupported Git version (unparseable); acquisition requires 2.43.7 or a patched release at least 2.50.1 on a newer track

Observed on main (0b016e4b) on 2026-10-26 with an empty environment and a PATH holding no git.

The refusal itself is correct and well behaved: exit 1, no traceback, no local path, and no cache directory created. Only the wording misleads, because it blames the version of a program that is not there. Say that git was not found, and keep the floor sentence for a git that is present but too old.

Low priority: it costs a reader one wrong guess, and it cannot reach anyone browsing a plain folder, which needs no git.
