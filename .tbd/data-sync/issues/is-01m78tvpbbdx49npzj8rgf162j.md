---
type: is
id: is-01m78tvpbbdx49npzj8rgf162j
title: "PR #379 C2: the spec does not record the seven accepted deviations"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:13.962Z
updated_at: 2026-11-12T22:38:58.244Z
started_at: 2026-11-12T21:33:39.716Z
closed_at: 2026-11-12T22:38:58.243Z
close_reason: "Fixed in 7adc990a on claude/shift-key-reveal-spec (#365): the spec records the seven accepted deviations and this round's changes. Reply: https://github.com/jlevy/metabrowser/pull/379#issuecomment-6837880362"
resolution: null
duplicate_of: null
---
Low. PR #379, review C (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899630). The spec on PR #365 (docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md) still says createShellKeymap() owns the main tab targets (spec:599-603, :924), the keyup listener passes only Shift (spec:446-447), only commitViewTabs() syncs in renderFile (spec:565-576, :936), and is silent on conditional W/X/A registration, active-scope live snapshots (spec:524-528, :1370), and the three-part golden (spec:1401-1404).
