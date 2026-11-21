---
type: is
id: is-01m7zns1bf05k1tz1rpd9ssrkh
title: Prevent the navigation Chrome fixture from accepting a different server on the same port
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-21T18:26:55.943Z
updated_at: 2026-11-21T18:26:55.943Z
---
In Nightly soak run 44905073328 on main at 98c2dffd, both checkout and history fixture servers announced port 50071. The history server bound it, its generic readiness response was accepted for the checkout server, and the browser later timed out looking for the checkout Markdown link. The other four repeats of that shard passed. Ensure simultaneous fixture servers have distinct ports and readiness validates the expected served folder. Evidence: https://github.com/jlevy/metabrowser/actions/runs/44905073328/job/136848794099
