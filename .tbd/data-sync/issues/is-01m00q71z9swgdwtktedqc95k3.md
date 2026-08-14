---
type: is
id: is-01m00q71z9swgdwtktedqc95k3
title: Render folder totals immediately from the live directory index
kind: feature
status: open
priority: 1
version: 4
labels:
  - browser
  - inventory
  - performance
dependencies:
  - type: blocks
    target: is-01m00nzbv28s9cd2qjykjfdp8w
  - type: blocks
    target: is-01m00phs4p1dvrzhgay8fqvwwr
  - type: blocks
    target: is-01m00q31dkqwp66dvmy7qjnq7h
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T18:05:43.784Z
updated_at: 2026-08-14T18:05:44.787Z
---
Make complete directory Total and Ignored measures available synchronously when navigating between known folders so overview and treemap totals paint in the first frame without zero-to-value flicker.

Required behavior:
- Define one revisioned directory-totals record containing all-file count and apparent bytes, ignored-file count and apparent bytes, readiness, and terminal truncation or failure metadata.
- Compute and retain these measures during the inventory crawl and live ancestor updates instead of performing an O(subtree) aggregation on each folder click.
- Carry the record through initial tree and lazy-subtree envelopes plus live change patches, preserving wire validation and backward compatibility.
- Add a public SDK directory-totals store keyed by normalized path. Seed it from navigation snapshots, patch it from inventory events, and expose synchronous get plus subscribe behavior to folder plugins without private app.js access.
- When a known folder is opened, mount File Totals or treemap Totals from the matching complete cached record in the same render transaction. Do not clear to zero, render provisional values, or wait for the detailed rollup request.
- Keep totals readiness independent from File Types and treemap-detail readiness. Complete totals may render immediately while those bodies show their shared loading block until a complete detailed snapshot arrives.
- Reject a cached record whose path or inventory revision does not match the current navigation transaction. Rapid navigation and late responses must not flash totals from the previous folder.
- For a direct deep link or genuine cache miss, show no numeric placeholder. Delay the shared loading block by the existing loading-state threshold, then replace it atomically when complete totals arrive.
- Preserve explicit terminal truncation or failure context without treating an in-progress crawl as a completed zero or empty directory.
- Test root and nested navigation, lazy-loaded folders, ignored descendants, live add/remove propagation, direct URLs, cache misses, rapid clicks, stale revisions, first-frame DOM output, and absence of intermediate zero text. Include a click-path performance assertion that no subtree walk or extra totals fetch occurs on the cache-hit path.
