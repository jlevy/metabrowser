---
type: is
id: is-01m87jc50m2z1dpwj6fjwx8vkr
title: "PR #771 B1: text in a kept checkbox's checked/disabled value, or in a repeated attribute, is shown nowhere and not flagged source_only"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87jc2mpxdc0xf9nkft5s532
hold: null
hold_until: null
created_at: 2026-11-24T20:01:23.474Z
updated_at: 2026-11-24T20:05:00.744Z
started_at: 2026-11-24T20:02:00.407Z
closed_at: 2026-11-24T20:05:00.742Z
close_reason: 'Fixed in 296434035 on PR #771 (head a7edb89c3): _RawMarkup hides every later copy of an attribute and any kept value the render does not write (_shows_value); it reads an input as a box where KPress does (_kpress_keeps_box, trims ASCII whitespace, ASCII-only), and both allowlists match a checkbox type in ASCII letters only. Every bold probe row in review B is source_only true at block and file level; bare checked, checked="", checked="checked", CHECKED stay false. Mutations M0-M5 fail the new tests.'
resolution: null
duplicate_of: null
---
Medium, regression from 7731d0cc8. _RawMarkup.handle_starttag (markdown_projection.py:685-712) hides attributes by name only, so values on checked/disabled, repeated copies of type/checked/disabled, and a later copy on any tag pass as shown; Unicode lower() reads a Kelvin-sign type as a checkbox where KPress and browsers do not. Review: https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6046004852
