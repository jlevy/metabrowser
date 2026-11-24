---
type: is
id: is-01m87jcb6reprcgv6a4vf8stwv
title: "PR #771 B3: the server hardener reads a repeated attribute as its last, unlike every other reader"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87jc2mpxdc0xf9nkft5s532
hold: null
hold_until: null
created_at: 2026-11-24T20:01:29.799Z
updated_at: 2026-11-24T20:05:02.269Z
started_at: 2026-11-24T20:02:03.607Z
closed_at: 2026-11-24T20:05:02.245Z
close_reason: "Fixed in 495d9dd84 on PR #771 (head a7edb89c3): _Hardener reads dict(reversed(attrs)); test_both_sides_read_a_repeated_attribute_as_its_first checks server and browser parity on raw HTML with repeated attributes, and fails with dict(attrs)."
resolution: null
duplicate_of: null
---
Low suggestion. inert_html.py:701 values = dict(attrs). Read the first copy, dict(reversed(attrs)), with a server/browser parity test on raw HTML that repeats attributes. Review: https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6046004852
