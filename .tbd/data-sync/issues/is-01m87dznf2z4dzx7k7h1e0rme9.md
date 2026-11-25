---
type: is
id: is-01m87dznf2z4dzx7k7h1e0rme9
title: "Guided Review overview: show which changed files no step cites"
kind: feature
status: open
priority: 3
version: 2
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
labels: []
dependencies: []
parent_id: is-01m836c38mhwwhmnxwz2ydn61z
created_at: 2026-11-24T18:44:40.030Z
updated_at: 2026-11-25T03:53:15.577Z
---
D6 of security review D on #677 (a suggestion), deferred there.

A guide is the author's selection and reading order, and now the pull request's front page. Its steps show only the files and lines the author chose, and nothing on the page says which changed files no step cites, so a guide can walk a reviewer, or an agent reading the `guided-review` route through `metab --api`, past the part of a change that matters. #677 says so in the user guide's Trust section (D4); this bead shows it on the page.

Shape: when the route reads a step it already has the comparison's manifest (`_step_references` in guided_review.py), so the overview (step 0) can answer the count, or the list, of changed files that no item's references cite, and the page draws it under the step list with links into Changes. A stale guide answers it for its own pins.

Overlaps mb-uqwl (plan-2026-11-24-guided-reviews-skill.md on #785), whose `guided-review-check` route lists "the changed files no step cites" for a draft guide; build the computation once and use it from both. Needs a parity row and golden for the route field, and a mount-script line for the page.
