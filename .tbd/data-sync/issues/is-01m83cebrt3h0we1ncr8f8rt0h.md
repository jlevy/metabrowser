---
type: is
id: is-01m83cebrt3h0we1ncr8f8rt0h
title: "PR #723 A1: cells narrower than padding plus border draw wider than their rectangle"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836r7jghtaq3hc7q5cny9sw
created_at: 2026-11-23T05:00:46.741Z
updated_at: 2026-11-23T05:00:51.367Z
closed_at: 2026-11-23T05:00:51.354Z
close_reason: "fixed: in `01cfb5aab`: a cell's edge is an inset box-shadow (`--tm-edge`) instead of a border, and an unlabelled cell (`.tm-bare`) has no padding; confirmed by the new `tests/test_treemap_containment_chrome.py`, 163 escapes on the old stylesheet and 0 now"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/723, finding A1 (High): cells narrower than padding plus border draw wider than their rectangle.
