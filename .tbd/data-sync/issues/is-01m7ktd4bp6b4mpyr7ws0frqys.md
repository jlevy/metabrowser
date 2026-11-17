---
type: is
id: is-01m7ktd4bp6b4mpyr7ws0frqys
title: "PR #494 review A2: pin KPress's TOC insets that replaced the removed bridge"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:55.541Z
updated_at: 2026-11-17T04:19:32.659Z
started_at: 2026-11-17T03:57:10.856Z
closed_at: 2026-11-17T04:19:32.659Z
close_reason: "Fixed in 3f7f459c on #494: test_pinned_kpress_owns_the_toc_insets pins KPress 0.3.8's padding-inline-start base and step, the title inset, no hanging indent, and no host restatement; fails on 0.3.6 and on a restated host rule."
resolution: null
duplicate_of: null
---
Review A finding A2, Medium. The PR removed text-indent: 0 and six padding-left rules for .kpress-toc in static/styles.css; no test pins KPress 0.3.8's padding-inline-start values, the title inset, or the absent hanging indent. Add a pin beside test_pinned_kpress_owns_the_inline_code_base_style in tests/test_kpress_dependency_contract.py that fails if KPress restores the hanging indent or the old base and step, and checks the host restates none of it.
