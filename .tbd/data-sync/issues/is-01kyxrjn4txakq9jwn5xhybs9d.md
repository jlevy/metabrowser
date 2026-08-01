---
type: is
id: is-01kyxrjn4txakq9jwn5xhybs9d
title: "PR #19 review S3: remove formatting-sensitive CSS test anchors"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kyxrj3k0zm0d52vvjhnp4zzp
created_at: 2026-08-01T04:16:07.321Z
updated_at: 2026-08-01T04:16:07.321Z
---
S3 at tests/test_kpress_print_contract.py:103 and tests/test_syntax_palette.py:155: normalize or structurally parse selectors/rules instead of relying on an embedded newline or prose comment delimiter.
