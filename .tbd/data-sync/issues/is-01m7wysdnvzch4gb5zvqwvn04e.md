---
type: is
id: is-01m7wysdnvzch4gb5zvqwvn04e
title: "Markdown and structured-text rendering: front matter, diagrams, untrusted content"
kind: epic
status: open
priority: 2
version: 2
labels: []
dependencies: []
child_order_hints:
  - is-01m7wyspfffhwcfcze4mke8jjp
created_at: 2026-11-20T17:06:42.489Z
updated_at: 2026-11-20T17:06:51.500Z
---
Rendered Markdown (KPress), wiki links and transclusion, front matter, the structured YAML and JSON views, and Mermaid diagrams, in the trusted and the inert (untrusted) profiles. Landed: Mermaid in Markdown (#597) and in pull request text (#616), GitHub's layout attributes (#626), bounded front matter parsed off the event loop (#542), untrusted Markdown rendered in an inert child under a deadline (#527), and the remote-image policy (#644).

What remains: Mermaid waits on the owner testing and merging kpress#80, then the repin (mb-tbq9, mb-d515); inert documents' diagram layout (mb-htyq); YAML alias bounds in the structured viewer (mb-7th1) and its other defects (mb-hs06, mb-59mp); Markdown bounds, robustness and wiki follow-ups (mb-k8os, mb-k0s0, mb-fvs1, mb-286z, mb-cz9v, mb-m4u9); TOC and transclusion polish (mb-hpoq, mb-jt6l, mb-9q0a, mb-2nqa, mb-4el3); KPress follow-ups (mb-no22, mb-jue2, mb-gc3c, mb-4cwy); and the front matter follow-ups from #542 (mb-2y6a, mb-ah1x, mb-s8bo, mb-993s). Nested: the inert-render hardening from #527 and the Markdown navigation evaluation (mb-fbm2).
