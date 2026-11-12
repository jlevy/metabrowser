---
type: is
id: is-01m748xv63xk4wtt5nrrr64s2q
title: "Host mode: ready line after bind, sticky port, stdin token, stdin-EOF exit, idle exit"
kind: feature
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xw1h1hx5p0eakfc0afgr
  - type: blocks
    target: is-01m748xvkxpj29cp9p8wr6vg5w
  - type: blocks
    target: is-01m748y1pa5yyy4wf2t16cpf0y
  - type: blocks
    target: is-01m774re9ewc3k6c8hp5x78376
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:52.354Z
updated_at: 2026-11-12T05:48:11.661Z
---
Phase 3, core metab. A JSON ready line printed after bind; a sticky port remembered per root with an OS-chosen fallback; a per-launch token on stdin; exit on stdin EOF; --idle-exit. Generalizes the draft VS Code host design (mb-x4y5); a reference-host test covers it.

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): the browser credential must not be a host-wide cookie: cookies are scoped by host and path, not port (RFC 6265 section 8.5). Choose a distinct loopback host name per server with host-only cookies, or a header token in origin-scoped storage, before issuing browser tokens.

2026-11-11, from review B on jlevy/metabrowser#352 (fixed in 5136540f): every client's credential, the app's web views included, must be bound to its origin: a distinct loopback host name per server with host-only cookies, or a header token in per-origin storage or handed only to a frame whose security origin matches. Acceptance: topology falsifiable claim 4 and the plan's Testing Strategy Credentials check (a page that loads from, is redirected to, or navigates to another server's port sends none of its credentials there, in the app's WKWebView, Safari, and Chrome).

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: the credential is a token in the Authorization header, never a cookie: one shell helper adds it only to requests for the page's own origin, with redirect: "error"; subresources, navigations, and EventSource carry none, so the first page load and the event stream need their own gate (one option: a shell without root data that fetches rows with the header, and the event stream read through a streamed fetch). Acceptance: topology claim 4 and the plan's Credentials check, including the same host name on another port.
