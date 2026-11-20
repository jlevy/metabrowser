- **SQLite databases open as SQLite, whatever their name.** A file that starts with
  SQLite’s 16-byte header opens in an Info view instead of Bytes: how Metabrowser read
  it and why, its page size and count, encoding, journal or write-ahead log, schema
  objects, `application_id` (an fsqlite snapshot is named), and the SQLite library
  against the reader’s minimum.
  A database named `History`, or with an extension no rule lists, is recognized too; a
  `.db` file that is not SQLite stays binary, and so does a compressed database.
  The file-type registry counts `.db`, `.sqlite3`, `.db3`, and `.s3db` as SQLite
  (revision 4). See [Reading Files](docs/browsing-files.md#reading-files).

- **Another application’s database is read without changing it.** Every connection runs
  in a separate reader process, never in the server, and opens the database by what it
  finds beside it: a rollback-journal database and an idle write-ahead-log one with no
  lock, validated against a commit; a log an application has open through its index; a
  log with no index, one no application has open (an owner that crashed, a copied
  folder), or a file with a second name, through a private copy.
  Metabrowser never writes to the database, its log, or an index no application holds,
  never creates or removes a file beside it, never rolls back another process’s journal,
  and never takes a lock that could refuse the owner’s commit; while the owner is
  writing, the view says so.
  See
  [Reading SQLite Databases](docs/project/architecture/arch-plugin-system.md#reading-sqlite-databases).

- **Plugins can claim a binary format by its magic number.** A `[[kind]]` match may name
  `magic = { offset, hex }`, checked on every file that would otherwise be `binary`,
  whatever its name; `ext` or `exts` beside it decide only the tree’s chevron.
  See [Kind Rules](docs/plugins.md#kind-rules).

- **The pull request catalog no longer drops its own locks.** A read of the catalog in
  one thread of the server could release the lock another thread’s write held, so a
  second Metabrowser process sharing the cache could read a half-written catalog; every
  handle on the catalog now closes after the last connection to it.
