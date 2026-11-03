---
type: is
id: is-01m6fggjanbkpgm012b76jt7q5
title: "PR #284 C9: name only the asked file in a single-file pathspec and let -C find the source"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:22.836Z
updated_at: 2026-11-03T02:31:10.917Z
closed_at: 2026-11-03T02:31:10.916Z
close_reason: "C9 rebutted: a one-path pathspec turns a copy into an add (git diff --raw -M50 -C -- Y.txt answers A Y.txt); the partner stays and --diff-filter=RC drops its own section."
resolution: canceled
duplicate_of: null
---
Low suggestion. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. git.py:181-192. Measure before choosing; C1 fix does not need it.
