---
type: is
id: is-01m836c3s4g6cj64za6cn5t3ya
title: "Phase 1: rename Guided PR's format to Collection/v1 inside #677 before it merges"
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/677
    at: 2026-11-23T03:51:31.438Z
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m836c49avbz4gszkp21yzrxf
parent_id: is-01m836c38mhwwhmnxwz2ydn61z
hold: null
hold_until: null
created_at: 2026-11-23T03:14:41.572Z
updated_at: 2026-11-24T18:06:07.156Z
started_at: 2026-11-23T03:14:44.322Z
---
Owner decisions 2026-11-23 (all brief recommendations): contract metabrowser.collection:Collection/v1, envelope 'collection'; keep the three-line softschema header; keep only the 'guided-pr' fence; fields feature->summary, architecture->overview, steps->items, commentary->note; MAX_STEPS->MAX_ITEMS; rename the route answer fields to match (step and step_count stay); keep UI headings 'What this changes' and 'Architecture'; do not split guided_pr.py yet (phase 2); leave CSS/JS internal names. Schema file regenerated via compile_model as collection-v1.schema.yaml. Update tests, goldens (make golden-update), docs/reviewing-pull-requests.md, arch-github-pull-requests.md, parity rows, changelog.d/mb-yakh.md, working-with-agents.md, and #677's description. #677 must stay mergeable alone and strictly additive to the rest of the release.

## Notes

Implemented in #677 at eada48cc9: contract metabrowser.collection:Collection/v1, envelope collection, fields summary/overview/items/note, MAX_ITEMS, schema regenerated as collection-v1.schema.yaml, route fields renamed, docs/tests/goldens updated. make verify: all green except 10 root-container failures that also fail on main. #677's description now carries a Collection/v1 guided-pr block pinned to eada48cc9 / merge base ec2b5422f, validated with parse_guide and per-range hunk checks; an end-to-end metab read was not possible here (container Git 2.43.0 is below the acquisition floor). Close when #677 CI is green.

2026-11-24: the owner reversed two of the 2026-11-23 decisions when naming the feature guided reviews ("Yes, rename now"): the fence is now guided-review, not guided-pr, and the route, modules, CSS classes, and JS names follow (acfcaa17d in #677). The owner also directed that the collection format stay general, not tied to pull requests or review: docs/project/architecture/arch-collection-format.md records the format/carrier split. Review C (C5) asked for this record.
