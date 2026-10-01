---
type: is
id: is-01m3vt1xj71w8xd6jfyp38k3fd
title: "Inert Markdown: the server keeps a link scheme's case and the page lowercases it"
kind: bug
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T13:21:56.294Z
updated_at: 2026-10-01T13:21:56.294Z
---
Found while adding the hostile-link corpus in PR #258: for a link written 'HTTP://example.com', inert_html.py keeps the scheme's case and static/inert-html.js lowercases it. Both keep the link, and both refuse the hostile schemes in tests/fixtures/inert-html-hostile-links.json, so this is not a safety issue; but the two layers are meant to produce the same markup (the allowlist parity tests compare them), and the corpus uses lowercase for the two kept links to keep exact-markup parity. Make the layers agree (lowercase in both, as URL parsers do) and add a mixed-case kept link to the corpus.
