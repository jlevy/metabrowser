---
type: is
id: is-01kxnvq1y0qwm9p57jcj37q09b
title: "PR #3 review D: extend the strict Content Security Policy to the default profile"
kind: task
status: open
priority: 3
version: 9
spec_path: TODO.md
labels:
  - pr-review
  - security
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:21:19.936Z
updated_at: 2026-11-14T18:44:53.825Z
extensions:
  linear:
    id: 4adbc1fb-afe9-4f50-9f55-e8ff34227388
    linked_at: 2026-08-16T08:05:50.437Z
---
Owner review SEC-1 from https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Since 0.12.0 the application page sends a strict Content-Security-Policy under the untrusted profile (--untrusted / --no-active-content): capabilities.untrusted_shell_csp, applied in server.py with a per-response nonce on the shell's inline scripts. No inline event handler remains in the shell or the built-in plugins. The default trusted profile still sends no CSP. Remaining: choose and apply a policy for the default profile that keeps the HTML preview frame and active content working, with tests for both profiles. Defense in depth; the reviewed XSS sink is fixed.

## Notes

Deferred intentionally after review: a nominal strict CSP would break the current inline shell/plugin handlers. The existing reviewed XSS sink is fixed; complete CSP work remains public and nonblocking until handlers are removed or nonce-enabled.

Scope note (2026-08-06): this bead is the *application shell* CSP and stays blocked on removing or nonce-enabling inline shell/plugin handlers. It is NOT blocked on, and does not block, mb-cun0, which attaches a CSP sandbox directive plus nosniff to /raw responses. Those responses contain no inline handlers, so the highest-risk endpoint gets a real policy without waiting for the shell refactor. See plan-2026-08-06-html-rendering-and-trust-model.md.

2026-11-14 audit: the untrusted-profile shell CSP landed in 386e3bb09 (0.12.0) and no inline handlers remain in src, so the 2026-08-06 scope note's blocker is gone; only the default profile lacks a policy.
