---
type: is
id: is-01m7ktd4bp6b4mpyr7ws0frqys
title: "PR #494 review A2: pin KPress's TOC insets that replaced the removed bridge"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:55.541Z
updated_at: 2026-11-17T03:57:10.856Z
started_at: 2026-11-17T03:57:10.856Z
---
Review A finding A2, Medium. The PR removed text-indent: 0 and six padding-left rules for .kpress-toc in static/styles.css; no test pins KPress 0.3.8's padding-inline-start values, the title inset, or the absent hanging indent. Add a pin beside test_pinned_kpress_owns_the_inline_code_base_style in tests/test_kpress_dependency_contract.py that fails if KPress restores the hanging indent or the old base and step, and checks the host restates none of it.
