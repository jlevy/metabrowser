- `METABROWSER_ORIGIN_STORE=0` keeps a repository folder, served or opened with `--api`,
  `--show`, or `--ref`, from keeping a store of its origin, so the folder lists its own
  remote-tracking branches and nothing is fetched for it unless a reader asks for a pull
  request’s comparison, which still makes the store
  ([environment variables](docs/command-line.md#environment-variables)).
