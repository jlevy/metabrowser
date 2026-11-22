- JSON and YAML files gain a **Table** view (`A`), beside Tree, still the default, and
  Source. A file whose top level is a list of mappings, such as an export of records or a
  YAML list of entries, opens there as a table: one row a mapping, one column a key, in
  the order each first appears, typed from its values.
  It sorts, filters, searches, and opens a row’s record as a CSV file’s table does, and
  a nested mapping or list is its JSON in the table and a collapsible tree in the
  record. Any other document says in the tab that it is not a list of records, and why.
  Table and Tree share one parse in either order, and a file opened first in Table
  parses without writing the copy as YAML that Tree offers, which was most of a large
  file’s first open; Tree writes it from that parse when first shown.
  A nested value is read only as far as a cell, a record, or a filter shows it, so YAML
  aliases cannot make a query cost far more than the file.

- **Plugin SDK:** `mountTable(container, {path, renderJson})` takes a function that
  draws a JSON value into an element and returns a handle with `dispose()`; the record
  draws each nested value with it, and the structured plugin passes its inline tree.
  A table whose source refuses the file (`source_unreadable`) shows the source’s words
  in place of the table, with no way back to a whole table it does not have.
