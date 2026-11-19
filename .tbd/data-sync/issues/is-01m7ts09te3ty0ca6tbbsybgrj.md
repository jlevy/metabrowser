---
type: is
id: is-01m7ts09te3ty0ca6tbbsybgrj
title: Structured JSON event log with latency for every request and background job, browsable in Metabrowser
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T20:47:07.583Z
updated_at: 2026-11-19T20:47:07.583Z
---
Owner, 2026-11-19, verbatim: "also I'm seeing cases where data like the PR diff summary are not loading after many seconds, is latency like this captured in our logs correctl so we can debug and identify when it happens always" and "that's another important requirement, you can file a bead for it and make sure we have a new subagent working on that too. the goal would be to have a clean json log that we can browse in metabrowser itself in different ways, wiht a full ui based on the logs of metabrowser, but initially it's okay if it's an internal log to facilitate debugging. itshould be both." Today (docs/realtime-debugging.md): Server-Timing headers; a stderr text warning for requests slower than METABROWSER_SLOW_SERVER_MS; METABROWSER_REQUEST_LOG=verbose; browser perf.js console messages. Background work the page waits on (GitHub fetches, PR diff summaries) is not timed as a request.
