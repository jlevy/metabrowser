---
type: is
id: is-01m75fzpspek15x7d5dqhnc2yw
title: Render untrusted Markdown in the projection child under a wall-clock deadline, no size cap, visible fallback to Source
kind: task
status: closed
priority: 2
version: 8
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-11T14:25:27.861Z
updated_at: 2026-11-17T22:00:26.101Z
started_at: 2026-11-17T18:30:16.884Z
closed_at: 2026-11-17T22:00:26.100Z
close_reason: Done in jlevy/metabrowser#527 (claude/inert-markdown-worker); handed to the landing coordinator
resolution: null
duplicate_of: null
---
Follow-up from stack #350 (PR #348 reviews C1/F1-F3, #347 review D2), merged 2026-11-11. The revision page's full-file Markdown render (builtin_plugins/github/pull_snapshot.py) runs in a thread under a whole-document work estimate (_DOCUMENT_WORK_MS = 400). An estimate is not a deadline. Review G on #348 found that Pygments has no text-size bound: a 1.6 KB console line took 12 s in the shell session prompt pattern, and 15 of 594 lexers are quadratic in a line's length (48 KB of devicetree took 79 s), some of it inside one re match that holds the GIL. So neither a thread nor asyncio.to_thread with a timeout can stop such a render or keep the event loop running. Meanwhile the page renders fenced code unhighlighted (render_kpress_view(plain_code=True)), and the estimate charges code as text.

Route the document render through a killable child process with a deadline, as metabrowser.diff.markdown_projection_worker already does for Markdown redlines. Keep the estimate as the first check, restore highlighting in the child, and measure first-render latency against the thread path.

## Notes

If mb-a9ek is closed, reparent to mb-2iok.

2026-11-17 coordinator: review A of #511 (View on branch) measured PR-authored Markdown on the pinned render route with no deadline or concurrency limit: 64 KiB task list 7.0 s, 256 KiB run of '[' 17.9 s. #511 removes the bounded revision page, so do not cut a release between #511 and this bead's PR (#527). Review A recommends the dedicated security and performance reviews go on #527.
