- A folder that is a repository’s root now lists its origin’s branches and tags as
  Metabrowser last fetched them, from a store of its own beside the checkout that
  borrows the checkout’s objects, and fetches that store in the background while the
  folder is served. The **Remotes** and **Tags** lists say when it was fetched, or why
  the origin is not fetched; choosing an origin branch shows it at the origin’s commit
  and follows it. The checkout is never fetched into or written
  ([browsing history](docs/browsing-history.md)). `GET /api/source/refs` answers the
  store’s state as `origin`, and `POST /api/source/refresh` on such a folder fetches the
  store.
