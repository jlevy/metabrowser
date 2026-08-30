---
type: is
id: is-01m0jsxgty51qvw61s6sfwv688
title: Close every gap row and make check_parity reject them
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:16.829Z
updated_at: 2026-08-30T00:53:42.688Z
---
The ratchet closes: flip each gap row in the parity table to a command and a golden, then remove the gap allowance from devtools/check_parity.py so a new route cannot land without its CLI equivalent. A parity check that permits gap rows forever is a check nobody reads.

## Notes

Remaining work as of 2026-08-28, after the parity mechanism landed: the table stands at 21 covered, 1 gap, 2 exempt (from 2 covered, 20 gap).

The single gap is /api/kpress/export. Its refusals are pinned in cli-api-shell.tryscript.md (405 on GET), but the success path writes a file to a caller-named destination, and every other metab mode is read-only. Closing it needs a policy decision first: may a golden perform a write, and where does the written file live so the transcript stays deterministic? That is a decision about the suite, not about one transcript.

Once that is settled and the row flips to covered, this bead's other half applies: make check_parity.py reject gap rows entirely rather than counting them.
