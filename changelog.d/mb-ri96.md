- **A native stack can have a guide of its own.** A `stack-review` block in a layer’s
  description, usually the top layer’s, is one guided review of the whole stack, read
  against the stack’s comparison.
  The stack’s page then leads with a **Guided Review** tab and opens on it, starting at
  its first step; the layer’s Conversation leaves the block out and shows a card that
  opens the stack’s page.
  The guide is read at the comparison the page shows, as its other tabs are.
  It stays on screen while a layer is fetched, and is read again, out of date where a
  layer moved past its pins, when you take the stack’s new comparison; until then, a
  step re-pinned for the new comparison says the stack has moved.
  The agent skill’s **Write a Stack Guide** says what each step says and how to publish,
  confirm, and refresh one
  ([A Stack’s Guide](docs/reviewing-pull-requests.md#a-stacks-guide)).

- **Plugin routes:** `GET /api/plugin/github/guided-review?stack=<n>&step=<k>` answers a
  stack’s guide in the envelope a pull request’s guide has, naming its `stack`, its
  `carrier`, the member whose description holds the block, and that member’s page as
  `carrier_url`; it answers `stack_unavailable`, with the stack’s `reason`, for a stack
  this copy cannot pair, and `not_cached` while a member is unread.
  `left`, `right`, and `key` read it at a comparison the `stack` route gave, current or
  kept, as `stack-comparison` takes them; one it never gave is `stack_moved`, as is a
  kept one the guide’s pins are past.
  Naming both `number` and `stack` is a 400. `GET /api/plugin/github/stack` names that
  member in `guide`, its `number` and record `revision`, or null.

- **Command line:** `--show /stack/<n>` reports the stack’s guide as `guide=#<member>`
  and the tab its front page shows, and `/stack/<n>/guided` is a stack page address.
