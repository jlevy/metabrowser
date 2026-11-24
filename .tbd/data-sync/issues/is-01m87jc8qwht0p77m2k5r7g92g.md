---
type: is
id: is-01m87jc8qwht0p77m2k5r7g92g
title: "PR #771 B2: the kpress==0.3.10 supply-chain row omits sanitizer and parser changes and the bound that contains them"
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
created_at: 2026-11-24T20:01:27.289Z
updated_at: 2026-11-24T20:05:05.466Z
started_at: 2026-11-24T20:02:01.836Z
closed_at: 2026-11-24T20:05:05.464Z
close_reason: "Fixed in a7edb89c3 on PR #771: the kpress==0.3.10 row names the button/form, footnote-note, body_html, svg-fence and task-marker changes, and the bound (Metabrowser allowlist after KPress on every untrusted path). check_supply_chain passes."
resolution: null
duplicate_of: null
---
Low. SUPPLY-CHAIN-SECURITY.md:56. Add one clause naming KPress 0.3.10's other sanitizer and parser changes (button type, form, footnote notes, body_html, svg fence inputs, task markers) and that Metabrowser's allowlist runs after KPress on every untrusted path. Review: https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6046004852
