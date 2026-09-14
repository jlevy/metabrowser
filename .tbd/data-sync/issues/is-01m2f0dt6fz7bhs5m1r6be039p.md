---
type: is
id: is-01m2f0dt6fz7bhs5m1r6be039p
title: "PR #113 review R3: body-read failure after headers is reported as a file error with no retry"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:28.078Z
updated_at: 2026-09-14T04:40:33.110Z
closed_at: 2026-09-14T04:40:33.109Z
close_reason: "Fixed in d454320f: responseBodyFailure marks body-read rejections unreachable (aborts, SyntaxError pass through); used for resp.text() and resp.json(); session cases."
resolution: null
duplicate_of: null
---
PR #113 review R3 (Low). src/metabrowser/static/app.js:5319-5323 (resp.text()), :5329-5333 (resp.json()), navigation.js:745-750. A server that stops mid-body rejects outside the marked fetch; pane shows 'Could not open this file.' and phase error never retries. Fix: responseBodyFailure(error) helper in navigation.js passing AbortError and SyntaxError through and wrapping the rest in ServerUnreachableError; apply to both reads; add a session case. Leave asset-load failures.
