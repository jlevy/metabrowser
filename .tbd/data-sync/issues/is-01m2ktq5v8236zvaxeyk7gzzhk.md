---
type: is
id: is-01m2ktq5v8236zvaxeyk7gzzhk
title: "Hosted releases R1 review: publish the GitHub mapping PR"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktprcgghmr7z8mpshmymcd
  - type: blocks
    target: is-01m2ktvrasq8fxf38pn3yf1p8j
parent_id: is-01m2ktprcgghmr7z8mpshmymcd
created_at: 2026-09-16T00:43:55.623Z
updated_at: 2026-11-14T18:46:03.887Z
closed_at: 2026-11-14T18:46:03.886Z
close_reason: "Obsolete: publication bead for the retired R1 mapping PR; re-planned release work under mb-7srn would get its own review beads."
resolution: canceled
duplicate_of: null
---
After independent technical review of Release R1 GitHub mapping, resolve every finding through the review shortcut, run make verify, and create or update the formal draft PR with gh stacked on the exact green R0 head. Before closing, record the exact PR URL, base/head branch names, immutable base/head OIDs, review record, final green CI, and registration with mb-kk47. Do not merge; mb-kk47 alone owns approval-gated landing.
