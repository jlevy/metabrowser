---
type: is
id: is-01m748xv63xk4wtt5nrrr64s2q
title: "Host mode H8: per-launch stdin token, first-load and event-stream gates, and the Credentials check"
kind: feature
status: open
priority: 2
version: 22
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xxadyc5tfdj366df1ag0
  - type: blocks
    target: is-01kxrygx61r5j6rakwqtq7dh74
  - type: blocks
    target: is-01m748xsest94amc9cyx26j1zk
parent_id: is-01m7wysrh5ggf7dm4xvqm8dmmp
created_at: 2026-11-11T03:02:52.354Z
updated_at: 2026-11-20T17:21:55.428Z
---
Host mode plan step H8, the token (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan; Decisions HM-1 A and HM-5 C, taken 2026-11-19). Last of Stack H, after the control socket (mb-1zyp), so gating a server never removes agent access that discovery and the view slice gave.

Delivers: first, a measurement of what the first-load gate costs against the unchanged build; then a per-launch token read from the first line of stdin and required in the Authorization header on every content route, appearing nowhere else (no argument, variable, log, or record); the shell's one helper that adds it only to requests for the page's own origin, with redirects refused; a first page that holds no root data, and an event stream read by a streamed fetch with the header; and the Credentials check in each engine it names before any token is issued. Hosts first, then every server once the first-load gate is measured (HM-5 C). The stdin-EOF exit already ships as metab --exit-on-eof (jlevy/metabrowser#366, src/metabrowser/cli/stdin_lifeline.py), which the app passes to every server. Generalizes the draft VS Code host design (mb-x4y5); a reference-host test covers it.

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): the browser credential must not be a host-wide cookie: cookies are scoped by host and path, not port (RFC 6265 section 8.5). Choose a distinct loopback host name per server with host-only cookies, or a header token in origin-scoped storage, before issuing browser tokens.

2026-11-11, from review B on jlevy/metabrowser#352 (fixed in 5136540f): every client's credential, the app's web views included, must be bound to its origin: a distinct loopback host name per server with host-only cookies, or a header token in per-origin storage or handed only to a frame whose security origin matches. Acceptance: topology falsifiable claim 4 and the plan's Testing Strategy Credentials check (a page that loads from, is redirected to, or navigates to another server's port sends none of its credentials there, in the app's WKWebView, Safari, and Chrome).

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: the credential is a token in the Authorization header, never a cookie: one shell helper adds it only to requests for the page's own origin, with redirect: "error"; subresources, navigations, and EventSource carry none, so the first page load and the event stream need their own gate (one option: a shell without root data that fetches rows with the header, and the event stream read through a streamed fetch). Acceptance: topology claim 4 and the plan's Credentials check, including the same host name on another port.

2026-11-19: restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md; the owner took HM-1 to HM-6 on 2026-11-19). Previously titled "Host mode: ready line after bind, sticky port, stdin token, idle exit", described as "Phase 3, core metab. A JSON ready line printed after bind; a sticky port remembered per root with an OS-chosen fallback; a per-launch token on stdin; --idle-exit." This bead keeps the token, the first-load and event-stream gates, and the Credentials check (step H8). The ready moment and boot ID moved to mb-hhzd (H1), the server record and ready-line flag to mb-wpel (H2), idle exit to mb-k3yz (H5), and the sticky port to mb-e74k (H6). Dependencies: the edge with mb-1zyp is reversed, so this bead now waits on mb-1zyp (the socket before the token); it no longer blocks mb-5xi4, mb-w4kd, mb-bbod, or mb-obgj (mb-w4kd now waits on mb-e74k, mb-obgj on mb-1zyp, and mb-bbod on both); it now blocks mb-rtgh and mb-x4y5, the plan's H9, which follows H8.
