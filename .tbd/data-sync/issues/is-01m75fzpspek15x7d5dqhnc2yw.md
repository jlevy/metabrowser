---
type: is
id: is-01m75fzpspek15x7d5dqhnc2yw
title: Run revision-page Markdown renders in the projection child with a deadline
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-11T14:25:27.861Z
updated_at: 2026-11-11T14:25:27.861Z
---
Follow-up from stack #350 (PR #348 reviews C1/F1-F3, #347 review D2). The revision page's full-file Markdown render runs in a thread under a measured whole-document work estimate (_DOCUMENT_WORK_MS, 400 ms; worst admitted measured ~451 ms under load). An estimate is not a deadline: an unmeasured construct can still hold the GIL longer, and the estimator reads private Pygments prompt-regex attributes with a conservative fallback. PR #349 adds an isolated projection child process that can be killed on overrun. Route the revision page's document render through that child (or an equivalent stoppable renderer), keep the estimate as the first check, and measure first-render latency against the thread path. Waits on stack #350 landing.
