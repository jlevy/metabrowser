---
type: is
id: is-01kxsftwrbwwffjdyyjaaan9d0
title: "Docs: encode proxied-session GitHub/gh guidance (NO_PROXY recipe) in tbd shortcut and publishing doc"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-07-18T02:10:40.509Z
updated_at: 2026-07-18T02:14:52.859Z
closed_at: 2026-07-18T02:14:52.858Z
close_reason: "Guidance landed: forked setup-github-cli shortcut with the verified NO_PROXY+GH_TOKEN recipe and three-channel diagnostic model; publishing.md prerequisites corrected; merged to main with CI green (merged via gh itself using the documented recipe)."
---
Retrospective from the v0.1.1 release: agent conflated the git broker, the HTTPS relay, and direct egress; the fix is NO_PROXY for GitHub hosts + GH_TOKEN, and gh honors NO_PROXY natively. Forked setup-github-cli shortcut with the verified recipe and three-channel diagnostic model; corrected the publishing doc's platform-prerequisites paragraph.
