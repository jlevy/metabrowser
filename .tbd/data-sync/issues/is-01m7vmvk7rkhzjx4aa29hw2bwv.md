---
type: is
id: is-01m7vmvk7rkhzjx4aa29hw2bwv
title: "main is red: cli-ui-source-freshness golden pins /api/event-logs to the pre-#632 page pin"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-11-20T04:53:53.526Z
updated_at: 2026-11-20T05:10:56.868Z
closed_at: 2026-11-20T05:10:56.867Z
close_reason: "Fixed by regenerating cli-ui-source-freshness in PR #631 (ccd4f771b); main's next run should be green."
resolution: null
duplicate_of: null
---
After #632 merged (f61159ade), tests/golden/cli-ui-source-freshness.tryscript.md expects /api/event-logs to carry pin 42382ea (the page pin in #629's version of the scenario) while #632 changed the scenario's page pin to 66f65bf. A semantic merge conflict between #629's event-log row and #632's pin; deterministic. Fixed by regenerating the golden in PR #631 (mb-30xb).
