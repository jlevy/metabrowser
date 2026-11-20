- A repository’s mirror is kept in a directory named for the repository, such as
  `~/.cache/metabrowser/repository-stores/github-com-jlevy-markform-1bo2sp3ey2l`, where
  it was named by all 64 hexadecimal digits of an identity.
  The name is the repository’s readable name, its words joined by single dashes, and the
  first 11 characters of the mirror’s identity digest written in base 36 (`0-9a-z`):
  56.9 bits, which the arithmetic beside `STORE_KEY_SUFFIX_CHARS` sizes so that two
  mirrors on one machine are under one chance in a billion of taking the same first
  name, even at 10,000 mirrors, the most the cache lists, and with every repository name
  taken to be the same.
  Chance is not what keeps two mirrors apart: the identity each mirror’s `store.yml`
  records is read before a name is claimed or a mirror is opened, and a name another
  mirror holds is never shared, so that mirror takes a longer one.
  The main heading’s note reads
  `mirror in ~/.cache/metabrowser/repository-stores/<name>`, without the
  `/repository.git` every mirror ends in; its tooltip and `/api/source/status` still
  give the whole location, where `git -C <location> log --all` works.
  `/api/cache/stores` says each store’s `key`, is paged by it (`after` and `next_after`
  are keys, where they were identities), and reports `id` as `null` for a store whose
  record cannot be read.
  See [Store Keys](docs/project/architecture/arch-repository-cache.md#store-keys).

- Upgrading to the `f03` cache layout, which names mirrors as above: the first `metab`
  that opens a repository in an older cache renames each mirror where it stands, so
  nothing is cloned again.
  A mirror no source names keeps the words its old name had, or, when it had none, is
  kept as `unattached-<11 characters>`, and an entry the rename cannot read is named in
  a warning and left as it is.
  That first open writes to the cache, so the cache must be writable once; a read-only
  copy is not migrated.
  Until then `/api/cache/*` answers `migration_pending`, and the macOS app, which reads
  that route to know whether a repository is cached, asks its clone question once for a
  repository it already holds; opening the repository migrates the cache.
  A `metab` of an earlier release refuses a migrated cache and asks for an upgrade.
  Stop running `metab` servers before the first new `metab` opens a repository (the
  macOS app restarts its own).
  A server of an earlier release that is still running fails to read its mirrors until
  it is restarted, and a clone it has in flight during the upgrade is published under
  the old name, so that repository’s alias names a mirror no name holds.
  The next open of that repository clones it again and publishes it under its name, and
  the directory under the old name stays: rename it to its name first to keep that
  clone, or clear the cache.
