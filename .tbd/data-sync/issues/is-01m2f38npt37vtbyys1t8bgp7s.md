---
type: is
id: is-01m2f38npt37vtbyys1t8bgp7s
title: "Markdown: latch the shared Worker after a deterministic load failure (needs real-browser evidence)"
kind: task
status: open
priority: 3
version: 1
labels:
  - markdown
dependencies: []
created_at: 2026-09-14T04:37:05.369Z
updated_at: 2026-09-14T04:37:05.369Z
---
Follow-up from PR #114 review suggestion 4 (https://github.com/jlevy/metabrowser/pull/114#pullrequestreview-5193705916). acquireMarkdownWorkerClient() in src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js replaces a fatally failed client on the next request, so after a deterministic module Worker load failure (missing asset, CSP) every preprocessing request constructs a new Worker that fails; before PR #114 the failure latched once per mount. Latching needs to tell a load failure apart from a transient crash, and that requires real-browser evidence: which browsers throw from new Worker() versus fire an async error event for a missing or CSP-blocked module script, whether that event is distinguishable from a runtime crash, and what a failing construction costs per request. Measure in headless Chromium (and ideally Firefox/WebKit) before choosing a latch policy; mb-k8os tracks the real-browser harness.
