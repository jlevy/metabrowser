---
type: is
id: is-01m895wtqspvjm3sfhghs21gmw
title: "CI: install_node.sh fails when GitHub release-asset download returns 403 for actions/node-versions"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T11:01:47.380Z
updated_at: 2026-11-25T11:01:47.380Z
---
Run 45599614517 job 139154888841 (goldens and serial 3.14 2/3): devtools/install_node.sh:83-87 downloads Node 24.18.0 from https://github.com/actions/node-versions/releases/download/...; all 10 retries got HTTP 403 over ~90 s and the job failed before any test ran. Cause is GitHub's release-asset endpoint refusing the runner (rate limit or transient denial), not repo code. Consider a cache (actions/cache keyed on the Node version), longer backoff on 403, or setup-node's toolcache. Known cause: a rerun of the job is the remedy until fixed.
