---
type: is
id: is-01m2h3qzqep911zn6jwx7dmb9t
title: Refresh v0.11 hosted-review, GitHub, and repository-cache design
kind: task
status: closed
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2h6zqmt05nwpte4w0nqcc29
  - is-01m2h6zr5n6fbvykpk2sbze85a
  - is-01m2h6zrn4c2zb59etfy799kqx
  - is-01m2h6zs5ct57684ap3pxka1qc
  - is-01m2h6zspabyewwda5jzycd1q8
  - is-01m2h6zt4nsxpy4jhefk633y12
  - is-01m2h6ztkqmdvxkfd16pyajtkg
  - is-01m2h6zv2s7wq0v52pcacmbspt
  - is-01m2h6zvg5dj2pq3f72kn8pxgx
  - is-01m2h6zvvcz065ycz8x1ykeafm
  - is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-14T23:23:56.013Z
updated_at: 2026-09-15T01:57:53.901Z
closed_at: 2026-09-15T01:57:53.901Z
close_reason: "Completed the v0.11 design refresh and PR workflow on PR #125: current origin/main merged at dc232a39, all 24 deduplicated review beads fixed and dispositioned, implementation graph release-gated and synchronized, make verify and both pre-push gates passed, final CI is green, and the final review-channel sweep found no new comments, formal reviews, inline threads, or linked issues."
resolution: null
duplicate_of: null
---
Reconcile TODO.md, the repository-cache plan, hosted-review/GitHub plan, CLI-first delivery map, diff ownership, architecture docs, and tbd beads against the v0.10.0 baseline. Define the provider-neutral Hosted Review Format, SoftSchema/frontmatter artifact profile, gh-backed provider port, virtual PR navigation collection, cache lifetimes, v0.11 implementation phases, and deferred GitLab, issue, stacked-change, chooser, and large-repository work. Prepare the design PR and address its documented technical reviews.
