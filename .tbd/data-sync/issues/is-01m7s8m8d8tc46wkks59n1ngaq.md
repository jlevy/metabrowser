---
type: is
id: is-01m7s8m8d8tc46wkks59n1ngaq
title: "Site-neutral in-app web views: a web pane, per-site profiles, one shared website store, a generic page marker"
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7s8m8y3w8ktzkpxjfet7eba
hold: null
hold_until: null
created_at: 2026-11-19T06:41:41.287Z
updated_at: 2026-11-19T06:41:50.320Z
started_at: 2026-11-19T06:41:50.319Z
---
Owner, 2026-11-18, verbatim: "I don't want this to be tied specifically to GitHub. The tooling to have web views is something we may want for other purposes as well. For example, we might want to be able to save bookmarks or other web pages and then browse through them using nav if we have support for that." Decisions (owner, 2026-11-18): one shared website data store for every in-app site, kept at the existing identifier so nobody is signed out, with Clear Website Data… clearing one site or all; scope is the native layer plus the page contract: a site-neutral web pane a popover (and later a window) hosts, a per-site profile (domains that stay, pages the marker may open), and a generic page marker. GitHub is the first profile. Bookmarks browsed in nav is a separate bead.
