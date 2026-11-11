---
type: is
id: is-01m75d7sftd3cvptte61dvmsbe
title: "PR #348 F3: highlighted code is charged by the byte, half of token-dense code and six times console fences"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75d7enb9z11kt1ge773zz3r
hold: null
hold_until: null
created_at: 2026-11-11T13:37:27.033Z
updated_at: 2026-11-11T14:23:40.109Z
started_at: 2026-11-11T13:37:36.647Z
closed_at: 2026-11-11T14:23:40.108Z
close_reason: "Fixed: d52784f7. Highlighted code charged by the lexer KPress applies: 31 us a token for code lexers, nothing for unknown/plain, session lexers only their commands plus a prompt-backtracking bound (_prompt_steps; Pygments' prompt pattern took 11.2 s on one 4 KB console line the old estimate admitted at 82 ms). Fences in quotes and list items are found; the scan errs toward charging more. Worst admitted render 451 ms at load 16-19 (prose 28-30 ms vs 24 ms quiet); 0/346 repo and 0/64 node_modules docs refused, 1/441 external. Tests: misread test (17 shapes), ordinary-docs test with two console goldens."
resolution: null
duplicate_of: null
---
Review F3 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858785036): Ruby 'a,' admitted at 25.8 KB renders 793 ms; seven tryscript goldens with console fences (36-61 ms renders) open as Source.
