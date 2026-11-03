---
type: is
id: is-01m6fgggsr8ctb5dn6bjhpx1ze
title: "PR #284 C5: diff.noprefix on a folder leaves a hunkless section nameless"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:21.271Z
updated_at: 2026-11-03T02:31:09.644Z
closed_at: 2026-11-03T02:31:09.643Z
close_reason: "C5 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: --src-prefix=a/ --dst-prefix=b/ --no-ext-diff on every patch run; adapter test."
resolution: null
duplicate_of: null
---
Low. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. patch_file.py:142-161; git.py:567-578. Pin --src-prefix=a/ --dst-prefix=b/ --no-ext-diff.
