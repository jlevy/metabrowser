- An open table follows its file: when a CSV or TSV file changes, even an ignored one or
  one deep in the folder, the table reads its rows again with the same sort, filters,
  and search, flashes the rows that changed or arrived, offers rows that would land
  above where you are reading instead of pushing the page down, and keeps your scroll
  position, focused row, open menus, and unsent filter text.
  A **Live** pill pauses it and counts the changes held back, and a read that fails
  keeps the rows last read and says so
  ([Live Updates](docs/browsing-files.md#live-updates)).

- A container in the tree, such as a patch file, reads its entries again when its file
  changes.

- Plugins can watch a file with
  `metabrowser.watchFile(path, {generation, onChange, onState})`, which registers it on
  the page’s one event stream rather than opening another; `fs.snapshot` now names its
  connection, and `POST /api/events/watch` registers a path on it, answers the
  generation a watch compares, and reports changes as `file.changed`
  ([File Watches](docs/project/architecture/arch-live-delivery.md#file-watches),
  [Plugin Authoring](docs/plugins.md)).
