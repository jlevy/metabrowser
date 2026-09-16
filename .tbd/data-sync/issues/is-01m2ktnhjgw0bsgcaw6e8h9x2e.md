---
type: is
id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
title: "Hosted releases: provider-neutral formats, GitHub cache, and composable views"
kind: epic
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - github
  - hosted-resources
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2ktnpypp52bxemwarsz57j6
  - is-01m2ktprcgghmr7z8mpshmymcd
  - is-01m2ktr3rq01pq9w0dpbvm1vpy
  - is-01m2kts81pnq5hh0xsb9465d22
  - is-01m2ktt8fsnkz860ze0f0ps2gm
  - is-01m2ktvrasq8fxf38pn3yf1p8j
created_at: 2026-09-16T00:43:02.095Z
updated_at: 2026-09-16T00:54:47.352Z
---
Add GitHub-first release browsing as the next proof of the general external-resource architecture, outside the initial v0.11 PR slice unless rescheduled explicitly. Define provider-neutral Release, ReleaseAsset, and ReleaseIndex SoftSchema contracts; map bounded gh api responses into the common provider store; cache direct release bundles before discovery; render transparent Markdown/YAML Source and rich Release views with exact tag revision content; then add a bounded Releases virtual collection. Reuse installed contract/resource-profile/resource-kind registries, auth-scoped immutable manifests, offline pointers, route/address parity, and nav paging. Each phase is one formal stacked PR with separate implementation and independent review/publication children.
