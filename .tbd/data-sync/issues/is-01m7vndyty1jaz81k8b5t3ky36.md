---
type: is
id: is-01m7vndyty1jaz81k8b5t3ky36
title: "main red: cli-ui-source-freshness golden keeps a stale /api/event-logs pin after #632 merged"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-11-20T05:03:55.229Z
updated_at: 2026-11-20T05:48:46.808Z
closed_at: 2026-11-20T05:48:46.808Z
close_reason: "Fixed on main by #638 (11196b040) with the same pin; #617 carried the identical change"
resolution: null
duplicate_of: null
---
Since f61159ade (merge of jlevy/metabrowser#632), goldens fail on main on every interpreter (run 44676764477): tests/golden/cli-ui-source-freshness.tryscript.md expects the /api/event-logs request's pin 42382ea2303b733e1e21b4bd6ddb974ca4e775eb but the session sends 66f65bf1e89dd9fdaeccc5377b2a342aa3fd2531. Cause: a semantic merge conflict. The event-log side (71e2d4789) recorded every pinned request at 42382ea; #632 (673cb8fd2) re-recorded the fixtures so the refreshed pin is 66f65bf; the merge kept the event-log side's /api/event-logs line. Fix: the expected pin is 66f65bf, as for /api/file and /api/tree in the same list. Reproduced locally on f61159ade with the single golden.
