---
type: is
id: is-01m6fvg6hjg91hmegfq5m3sg4b
title: Set a pull request's texts in sans; serif is for committed documents
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-03T04:43:25.104Z
updated_at: 2026-11-03T04:43:25.856Z
closed_at: 2026-11-03T04:43:25.854Z
close_reason: Merged forward through the stack; verified in Chrome on a public PR and on the owner's server.
resolution: null
duplicate_of: null
---
Owner's rule: chrome, content, and messages are sans; serif is reserved for committed document content rendered as a document when the reading font is serif. The pull request page's description, comments, and reviews were serif. Done on PR 280 at 996ea90d and merged forward (284 at 9d6e0930, 283 at 2a22035b): .github-pull points the KPress prose hook at --prose-sans-font and --doc-measure at the new --message-measure; design-system.md 'Serif Is for Documents'; test_serif_is_only_for_documents. Measured in Chrome: Source Sans 3 at 15px, 616px at 102 chars (618 expected sans, 663 serif); a Markdown file stays PT Serif.
