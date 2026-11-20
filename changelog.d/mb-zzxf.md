- An [fsqlite](https://github.com/jlevy/fsqlite) store opens as one: its `fsqlite.json`
  marker is the `sqlite-store` kind, and the tree badges the store’s folder.
  Its Info view shows the store’s format and identity, the version its `current` pointer
  names, the transaction envelopes waiting for the next reconcile, and that snapshot as
  a SQLite database’s Info view shows one, or the state of a store it cannot show
  (invalid, unsupported, or corrupt).
  Metabrowser reads a store as a guest: the snapshot with `immutable=1` in a reader
  process, no read lease, no lock, and no file written, and it reads the pointer again
  once when garbage collection removed the snapshot it named.
  `metab --api` reaches the same model at `/api/plugin/fsqlite/info`, and the store’s
  tree children, the snapshot’s tables once the SQLite source lists them, at
  `/api/plugin/fsqlite/children`
  ([Views, Models, and Routes](docs/project/architecture/arch-views-models-routes.md)).

- The SQLite plugin exports its Info view’s `infoModel` and `drawInfo` to a plugin that
  requires it.
