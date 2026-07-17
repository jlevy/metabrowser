---
type: is
id: is-01kxnvq1y0qwm9p57jcj37q09b
title: "PR #3 review D: add a strict Content Security Policy"
kind: task
status: open
priority: 3
version: 4
spec_path: TODO.md
labels:
  - pr-review
  - security
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:21:19.936Z
updated_at: 2026-07-17T20:20:45.328Z
---
Owner review SEC-1 from https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Add a strict Content-Security-Policy response header after removing or nonce-enabling the remaining inline script and handler requirements, including shell and built-in-plugin handlers. Defense in depth; the reviewed XSS sink is already fixed. This is nonblocking for v0.1.0 but must remain an explicit public follow-up if not safely completed in PR #3.

## Notes

Deferred intentionally after review: a nominal strict CSP would break the current inline shell/plugin handlers. The existing reviewed XSS sink is fixed; complete CSP work remains public and nonblocking until handlers are removed or nonce-enabled.
