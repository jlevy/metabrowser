- In a repository folder, the **Remotes** list now marks an origin branch where your
  checkout’s own `origin/<branch>` is not where the origin is as Metabrowser last
  fetched it: “yours differs” for a branch you have not pulled, or have pushed since,
  and “not in checkout” for one you have never fetched, with your commit in the row’s
  tooltip
  ([browsing history](docs/browsing-history.md#branches-and-tags-of-a-local-checkout)).
  `GET /api/source/refs?kind=remote` carries it as `checkout` on such a row: the commit
  and commit date of the checkout’s own ref, or nulls when it has none.
