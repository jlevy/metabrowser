---
type: is
id: is-01kxnvq1y0qwm9p57jcj37q09b
title: "PR #3 review D: add a strict Content Security Policy"
kind: task
status: open
priority: 3
version: 6
spec_path: TODO.md
labels:
  - pr-review
  - security
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:21:19.936Z
updated_at: 2026-08-16T08:05:43.091Z
extensions:
  linear:
    id: 4adbc1fb-afe9-4f50-9f55-e8ff34227388
    linked_at: 2026-08-16T08:05:43.091Z
---
Owner review SEC-1 from https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Add a strict Content-Security-Policy response header after removing or nonce-enabling the remaining inline script and handler requirements, including shell and built-in-plugin handlers. Defense in depth; the reviewed XSS sink is already fixed. This is nonblocking for v0.1.0 but must remain an explicit public follow-up if not safely completed in PR #3.

## Notes

Deferred intentionally after review: a nominal strict CSP would break the current inline shell/plugin handlers. The existing reviewed XSS sink is fixed; complete CSP work remains public and nonblocking until handlers are removed or nonce-enabled.

Scope note (2026-08-06): this bead is the *application shell* CSP and stays blocked on removing or nonce-enabling inline shell/plugin handlers. It is NOT blocked on, and does not block, mb-cun0, which attaches a CSP sandbox directive plus nosniff to /raw responses. Those responses contain no inline handlers, so the highest-risk endpoint gets a real policy without waiting for the shell refactor. See plan-2026-08-06-html-rendering-and-trust-model.md.
