---
type: is
id: is-01m7rc08e8rhfapch9mtg42aft
title: Pull request view shows raw Markdown for 3-4 s before it renders
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T22:21:25.831Z
updated_at: 2026-11-18T22:21:25.831Z
---
Owner, 2026-11-18: "when I open a PR view, I often see the content showing as raw Markdown, and then it can be a full 3 or 4 seconds before it actually renders and converts the raw Markdown to rendered Markdown. I don't know why that should take so long. There's really no excuse." Find what the PR view paints first, what it waits on before rendering Markdown (renderer bundle load tier, a fetch, the diff manifest, a lazy mount, a sequential await), measure it in a real browser on a real PR, and fix it so rendered Markdown is the first paint or arrives within a frame or two. Related principle: never flash an unrendered or spinner state under ~50 ms; prefetch by default.
