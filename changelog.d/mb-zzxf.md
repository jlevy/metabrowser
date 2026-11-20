- An [fsqlite](https://github.com/jlevy/fsqlite) store opens as one: its `fsqlite.json`
  marker is the `sqlite-store` kind, and the tree badges the store’s folder.
  A store is a container whose tables are those of the snapshot its `current` pointer
  names, each at `<marker>/<table>` as a SQLite database’s are, with the format’s
  `applied_tx` and `fsqlite_meta` grouped as internal tables.
  Its Table view is the store’s overview, or at a table’s address the table itself,
  sorted, filtered, and paged as any SQLite table; its Schema view shows the snapshot’s
  DDL; and its Info view shows the store’s format and identity, the version `current`
  names, the transaction envelopes waiting for the next reconcile, and that snapshot as
  a SQLite database’s Info view shows one, or the state of a store it cannot show
  (invalid, unsupported, or corrupt).
  Metabrowser reads a store as a guest: the snapshot with `immutable=1` in a reader
  process, no read lease, no lock, and no file written, and it reads the pointer again
  once when garbage collection removed the snapshot it named.
  `metab --api` reaches the same models at `/api/plugin/fsqlite/info`,
  `/api/plugin/fsqlite/schema`, and `/api/plugin/fsqlite/children`, and the tables
  through `/api/plugin/table/*` at the marker’s path
  ([Views, Models, and Routes](docs/project/architecture/arch-views-models-routes.md)).

- The SQLite plugin exports its Info view’s `infoModel` and `drawInfo`, and its Table
  and Schema views’ `mountTableView` and `mountSchema`, to a plugin that requires it.
