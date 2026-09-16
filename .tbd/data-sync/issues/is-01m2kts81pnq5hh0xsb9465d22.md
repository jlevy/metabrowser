---
type: is
id: is-01m2kts81pnq5hh0xsb9465d22
title: "Hosted releases R3: direct release document and asset children"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2kttf7tse7rs1nwrk9m3jbj
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
child_order_hints:
  - is-01m2ktsfdmrdehcpvg9kqsg6yb
  - is-01m2ktsmf38rkaje935qzed4fp
created_at: 2026-09-16T00:45:03.412Z
updated_at: 2026-09-16T00:54:48.969Z
---
One formal PR stacked on green R2. Register the release resource kind and generic /hosted address, then render Release and Source views from the same frontmatter artifact; compose untrusted Markdown notes, exact tag revision content, lifecycle metadata, partial/offline state, and cached asset children through existing selection, view, route, CLI, and container machinery.
