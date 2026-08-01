---
type: is
id: is-01kyxrjmcrtvgxez9y6xh067t7
title: "PR #19 review R3: pin TOC breakpoint to KPress contract"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kyxrj3k0zm0d52vvjhnp4zzp
created_at: 2026-08-01T04:16:06.551Z
updated_at: 2026-08-01T04:16:06.551Z
---
R3 Low at src/metabrowser/static/styles.css:2020 and tests/test_kpress_print_contract.py:157: Metabrowser duplicates KPress 75rem document band without verifying the installed KPress asset. Add an upgrade-time contract assertion.
