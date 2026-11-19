---
type: is
id: is-01m7s7p50603be3efeagnhavr0
title: Commit message bodies render as Markdown, as pull request descriptions do
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:25:14.746Z
updated_at: 2026-11-19T06:42:13.794Z
started_at: 2026-11-19T06:25:33.935Z
---
Owner, 2026-11-18, verbatim: "can we format git commit message long descriptoins robustly as markdown, just like PR reqeust descriptoins?"

## Notes

2026-11-18 progress (branch claude/commit-body-markdown):
- Reused path: the PR description's. New core route GET /api/git/commit-markdown/{revision} (git/message.py) renders the body via shared_worker().render_inert(InertRender(..., include_toc=off, link_base=...)) = KPress sanitized + inert_html.harden in the Markdown child under its deadline, plain code, plus kpress_adapter.document_stylesheets(). Page sets it through static/inert-html.js sanitizeHtml + kpressProse in article.kpress.kpress-inert inside .metabrowser-kpress-host, links via decorateExternalLink, as pull-page.js kpressHost does.
- Line breaks: CommonMark soft breaks (KPress, as for PR descriptions in Metabrowser): hard-wrapped prose reflows; no breaks:true.
- Trailers: last paragraph split off when every line is Token: value / folded continuation / cherry-pick note (git's all-trailers rule; not git's 25% Signed-off-by rule); answered verbatim as 'trailers', shown as a muted pre-wrap block.
- Links: base about:blank (COMMIT_MESSAGE_LINK_BASE): only absolute http(s) kept; relative/fragment/protocol-relative keep text. #123 and bare URLs stay text, as in PR descriptions (KPress links neither). Parity of server and browser for that base added to tests/test_inert_html.py.
- Bound: GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES = 64 KiB = pull_record.MAX_BODY_BYTES (test pins). Over it: 422 body_too_large, page shows the message as written + notice (no cut). Measured: largest body in this repo 9,105 B (p99 2,503); render+harden 64 KiB ~50 ms in process at load 22.
- Browser: plain body hidden (pending) until the render comes; prefetch on hover via prepareRevision; kept renders bounded by DETAIL_CACHE_SIZE; cleared on teardown.
