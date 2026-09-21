---
type: is
id: is-01m32f6gj1w0ze6vqp70ev6xa0
title: "PR #224 review R2: drift gate test_every_allowlisted_key_is_one_the_package_reads cannot fail"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m32f65s054qm967k3e28xjv9
hold: null
hold_until: null
created_at: 2026-09-21T17:11:11.681Z
updated_at: 2026-09-21T17:44:33.945Z
started_at: 2026-09-21T17:11:49.017Z
closed_at: 2026-09-21T17:44:33.945Z
close_reason: "Fixed in f7e5a71a (exp-036 re-measured in b479dc95). PR #224 review findings R1-R21 and S1: allowlist narrowed to the two names with total parsers, log-level parsing checked against VALID_LOG_LEVELS, dotenv_values replaces load-then-undo, _route_path mirrors starlette get_route_path, drift gate made falsifiable, HOME and serve-mode pins split, GIT_* end-to-end test added with GIT_TRACE as oracle, ignored names warned once per file, and the changelog/SECURITY/README/command-line/plugins/spec/exp-036 inaccuracies corrected."
resolution: null
duplicate_of: null
---
