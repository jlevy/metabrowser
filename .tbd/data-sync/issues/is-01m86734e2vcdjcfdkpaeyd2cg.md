---
type: is
id: is-01m86734e2vcdjcfdkpaeyd2cg
title: "lint-check exited 2 once on #771's release-pin commit and passed on two reruns; output was discarded"
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-24T07:24:59.189Z
updated_at: 2026-11-25T02:32:55.914Z
---
On 2026-11-24 ~07:20 UTC in the task-list-boxes worktree, make -o install lint-check exited 2 right after devtools.check_goldens passed, with output sent to /dev/null. Two reruns minutes later, one with the change committed and one with it only staged, exited 0. No time-dependent rule in check_supply_chain; the 08:00Z exemption date is not checked against now. Mechanism unknown: candidates are a network-dependent step or a shared cache (flowmark --check, biome, npx). Next time capture the output; if it recurs, find which of the lint-check steps exits 2.

## Notes

Likely mechanism (2026-11-24): lint-check ends with flowmark --check over the whole worktree, untracked files included. The same exit 2 reproduced on #677 from an untracked .md working copy ('Would reformat: .e2e-logs/g677/body.md'). On #771 the failing run came straight after tryscript --update rewrote tests/golden/cli-api-shell.tryscript.md, and the commit hook's format-markdown --inplace then reformatted the staged file, which is why both reruns, made after the commit, passed. Not proven: the original output was discarded. Confirm by running tryscript --update on that golden and then flowmark --check; if confirmed, golden-update should format what it writes.
