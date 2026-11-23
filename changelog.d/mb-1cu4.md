- `/api/rollup` takes three new parameters.
  `nodes` names the node budget, up to `ROLLUP_MAX_NODES`, or `max` for the bound; a
  request that names none keeps the default budget.
  `ignored=exclude` leaves gitignored entries out of `children` and `rest`, and they
  spend none of the budget, while every total, tally, and breakdown still counts them.
  `encoding=compact` writes each expanded folder’s files as positional `files` entries
  without their paths, 39% of the JSON’s bytes for a whole 38,000-entry tree; a pinned
  Git revision answers the default encoding.
  A folder now spends a share of the node budget left in proportion to what it holds, so
  one flat folder no longer takes the budget: at the default budget, that repository’s
  map left 19% of its area in unexpanded folders, where it left 52%, and a response
  whose budget binds emits a different set of nodes than before
  ([Plugin SDK](docs/plugins.md)).

- **Plugin SDK:** `fetchRollup` and `watchRollup` pass `nodes` (a positive integer or
  `"max"`), `ignored` (`"include"` or `"exclude"`), and `encoding` (`"json"` or
  `"compact"`) through to `/api/rollup`, and return a compact body undecoded
  ([Plugin SDK](docs/plugins.md)).

- The Treemap view draws much more of a large folder: it asks for the route’s largest
  node budget in the compact encoding, so on a repository of 38,000 entries the area
  left in unexpanded folders falls from about half the map to under 1%. With Show
  ignored off it asks without the gitignored entries, and turning Show ignored on or off
  asks again; the map keeps its drawing until the new tree arrives.
  The Overview’s compact map keeps the default budget.

- Treemap cells of equal size are now ordered by path, so the same folder draws the same
  way whichever order its rollup lists it in.
