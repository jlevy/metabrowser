---
type: is
id: is-01kxnvq1y0qwm9p57jcj37q09b
title: "PR #3 review D: add a strict Content Security Policy"
kind: task
status: open
priority: 3
version: 3
labels:
  - pr-review
  - security
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:21:19.936Z
updated_at: 2026-07-16T16:44:33.178Z
---
Owner review SEC-1 from https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Add a strict Content-Security-Policy response header after removing or nonce-enabling the remaining inline script and handler requirements, including shell and built-in-plugin handlers. Defense in depth; the reviewed XSS sink is already fixed. This is nonblocking for v0.1.0 but must remain an explicit public follow-up if not safely completed in PR #3.

## Notes

Deferred intentionally after review: a nominal strict CSP would break the current inline shell/plugin handlers. The existing reviewed XSS sink is fixed; complete CSP work remains public and nonblocking until handlers are removed or nonce-enabled.
