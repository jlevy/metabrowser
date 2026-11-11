---
type: is
id: is-01m75fzpspek15x7d5dqhnc2yw
title: Run revision-page Markdown renders in the projection child with a deadline
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-11T14:25:27.861Z
updated_at: 2026-11-11T15:18:52.200Z
---
Follow-up from stack #350 (PR #348 reviews C1/F1-F3, #347 review D2). The revision page's full-file Markdown render runs in a thread under a measured whole-document work estimate (_DOCUMENT_WORK_MS, 400 ms; worst admitted measured ~451 ms under load). An estimate is not a deadline: an unmeasured construct can still hold the GIL longer, and the estimator reads private Pygments prompt-regex attributes with a conservative fallback. PR #349 adds an isolated projection child process that can be killed on overrun. Route the revision page's document render through that child (or an equivalent stoppable renderer), keep the estimate as the first check, and measure first-render latency against the thread path. Waits on stack #350 landing.

Update from review G on #348 (round 3): Pygments costs no text estimate bounds. A 1.6 KB `console` line took 12 s in the shell session prompt pattern, and 15 of 594 lexers are quadratic in a line's length (48 KB of `devicetree` took 79 s), some of it inside one `re` match that holds the GIL. So the stoppable renderer has to be a separate process: a thread, or `asyncio.to_thread` with a timeout, can neither stop these renders nor keep the event loop running. Meanwhile the revision page renders fenced code unhighlighted, escaped as KPress shows a fence with no language (`kpress_adapter.render_kpress_view(plain_code=True)`), and the estimate charges code as text and no longer reads Pygments. Once renders run in a killable child with a deadline, this bead can restore highlighting there.
