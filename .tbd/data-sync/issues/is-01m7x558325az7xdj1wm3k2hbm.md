---
type: is
id: is-01m7x558325az7xdj1wm3k2hbm
title: "Guided PR: show the tab from the server's parse, and let an author validate a guide before publishing"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T18:58:01.441Z
updated_at: 2026-11-20T18:58:01.441Z
---
Guided PR (#599, bead mb-yakh) shows its tab from a client hint, not from the server's parse.

The page decides whether to show the Guided PR tab with GUIDED_FENCE in pull-page.js, a
regular expression over the cached description that matches any line opening a guided-pr
fence. The server's parse_guide() (guided_pr.py) counts only a top-level fence, so a
description that documents the format inside an outer fence shows the tab, and the tab
then says the pull request has no guide. Review A6 on #599 asked for the server's answer
to drive the tab. mb-yakh documents the disagreement and does not fix it, because the fix
is not small: a has_guide field on the pull route's envelope (PullEnvelope in
pull_route.py) changes every golden that prints an envelope, the field needs the parse
memoized by record revision (guided_pr.py now has one) so the hot pull route does not
reparse, and guided_pr.py already imports pull_route, so the check needs a third module.

Also open from A6: an author cannot validate a guide before publishing it. A small metab
mode, or a documented recipe, that runs parse_guide on a file would catch invalid YAML and
a wrong contract before the description is edited.

Done when: the tab and the parse cannot disagree (a test with a block inside an outer
fence), the pull route's cost on a large description is measured, and an author can check
a guide file without a pull request.
