---
type: is
id: is-01m2h3tm78x9jhg6b5s128jqy0
title: "PR #124 review R1: source-scoped memo maps allocated on the unmemoizable path"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2h3tchfkxfpw0am8k6m6dkr
created_at: 2026-09-14T23:25:22.536Z
updated_at: 2026-09-14T23:33:18.167Z
closed_at: 2026-09-14T23:33:18.167Z
close_reason: "Fixed in PR #124 (merged): wiki memo keys now stay inside V8's 16,383-code-unit content-hash bound, so the link enhancer session went from 32.3 s of CPU to 0.40 s and resolution is linear in targets. Review R1 fixed in 7bdc583a; R2 deferred as mb-e22r. CI green on all seven checks."
resolution: null
duplicate_of: null
---
src/metabrowser/builtin_plugins/markdown/wiki-resolver.js: when both the exact path and the authored target exceed MAX_MEMO_KEY_LENGTH, beginMembership allocated the source-scoped Maps and then dropped the references. Allocate only when the key is memoizable.
