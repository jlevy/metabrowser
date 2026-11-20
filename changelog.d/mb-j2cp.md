- A repository’s mirror is kept in a directory named for the repository, such as
  `~/.cache/metabrowser/repository-stores/github-com--jlevy--markform--589d51b16fd8f1a2`,
  where it was named by all 64 hexadecimal digits of an identity.
  The name is the repository’s readable name, the one its source directory has, and the
  first 16 digits of the mirror’s identity: 64 bits, which the arithmetic beside
  `STORE_KEY_SUFFIX_HEX_DIGITS` sizes so that two mirrors on one machine are under one
  chance in a billion of taking the same first name, even at 100,000 mirrors and with
  every repository name taken to be the same.
  Chance is not what keeps two mirrors apart: the identity each mirror’s `store.yml`
  records is read before a name is claimed or a mirror is opened, and a name another
  mirror holds is never shared, so that mirror takes a longer one.
  The main heading’s note reads
  `mirror in ~/.cache/metabrowser/repository-stores/<name>`, without the
  `/repository.git` every mirror ends in; its tooltip and `/api/source/status` still
  give the whole location, where `git -C <location> log --all` works.
  The cache layout is now `f02`, and the first `metab` that opens a repository in an
  older cache renames each mirror where it stands, so nothing is cloned again, and keeps
  one that no source names as `unattached--<16 digits>`. A `metab` of an earlier release
  refuses a migrated cache and asks for an upgrade, and a server of one that is still
  running reads the old directory names until it is restarted.
  `/api/cache/stores` says each store’s `key`, is paged by it (`after` and `next_after`
  are keys, where they were identities), and reports `id` as `null` for a store whose
  record cannot be read.
  See [Store Keys](docs/project/architecture/arch-repository-cache.md#store-keys).
