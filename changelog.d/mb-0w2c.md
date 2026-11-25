- **The Table tab appears only on a JSON or YAML list of records.** A file that starts
  as a list of mappings, or a YAML stream of mappings, has the tab; a mapping, a scalar,
  an empty list, or a list of anything else no longer shows a Table tab that says it is
  not a list of records.
  Metabrowser decides from the file’s first bytes, so a list that starts with a mapping
  but holds something else further on keeps the tab, which says why it shows no table.

- **Plugins:** a text file kind’s `[[view]]` may now set `offer`, a predicate given the
  file’s leading bytes and its extension, to serve the view only on the files it suits,
  as a folder view’s `offer` already could ([Views](docs/plugins.md#views)).
