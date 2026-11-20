---
type: is
id: is-01m7rc08e8rhfapch9mtg42aft
title: Pull request view shows raw Markdown for 3-4 s before it renders
kind: bug
status: closed
priority: 1
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/589
    at: 2026-11-20T17:05:42.730Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-18T22:21:25.831Z
updated_at: 2026-11-20T19:11:34.375Z
started_at: 2026-11-18T22:22:05.770Z
closed_at: 2026-11-19T00:47:03.266Z
close_reason: "Landed in #589 (ab324832d)"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 76ca2fe3-69d7-468a-b896-5c811ad92be4
    linked_at: 2026-11-20T18:01:13.570Z
---
Owner, 2026-11-18: "when I open a PR view, I often see the content showing as raw Markdown, and then it can be a full 3 or 4 seconds before it actually renders and converts the raw Markdown to rendered Markdown. I don't know why that should take so long. There's really no excuse." Find what the PR view paints first, what it waits on before rendering Markdown (renderer bundle load tier, a fetch, the diff manifest, a lazy mount, a sequential await), measure it in a real browser on a real PR, and fix it so rendered Markdown is the first paint or arrives within a frame or two. Related principle: never flash an unrendered or spinner state under ~50 ms; prefetch by default.

## Notes

PR #589 (claude/pull-view-markdown-first-paint). Cause: a pull request with no record opens on its core preview, and the page asked for no Markdown while showing one (markdownFor null, holdFirstPaint skipped cores, pull-markdown read records only), so the description stayed source until the record fetch landed and the next poll read it. Measured on this repo via the Pulls tab with cores prepared (load 22-28): source 4.2 s (584) and 2.8 s (583) before; after (load 32-33) no source frame, rendered at 325 ms and 95 ms from the click. Fix: pull-markdown renders the core description (core_revision); the page asks for it under textRevision and holds first paint for cores; past the 200 ms hold a placeholder (.github-pull-plain-pending) shows instead of source. Chrome test tests/test_github_pull_core_markdown_chrome.py fails on main, passes with the fix. Follow-ups: parallel KPress stylesheet loads in loadKpressAssets (~66 ms per document), Markdown child idle stop, 1.1-1.6 s core wait when a row is clicked before its core is prepared. changelog.d fragment depends on #585.
