- A SQLite database now lists its tables: it expands in the navigation tree like a
  folder, its Table view is an overview of its tables, views, and virtual tables with an
  estimate of each one’s rows, and each table opens at `<database>/<table>` in the table
  view, sorted, filtered, searched, and paged in both directions without reading the
  whole table. Every value is shown as stored: null apart from the empty string, an
  integer past what a browser number holds with its digits, infinite reals, text that is
  not valid UTF-8, JSON, blobs as hex, a value in a column of another type marked, and a
  long value previewed with its size.
  Declared foreign keys are references with hover cards, a value naming a missing row is
  marked missing, and a record counts the rows that reference it.
  A count past its cap is a lower bound, and on a large table only indexed fields sort.
  A filter or search on a large table reads a bounded window of rows at a time and says
  how many it read, continuing past them whether or not any matched.
  Virtual tables, and views that read them, are read only in a trusted folder; an R-tree
  is listed but not read.
  A new Schema view shows each object’s DDL, indexes, triggers, and foreign keys.
  Reading never changes the database or the files beside it.

- `metab --api` reaches every table at `/api/plugin/table/*?path=<database>/<table>`,
  and the new `/api/plugin/sqlite/schema` and `/api/plugin/sqlite/children` routes.

- Plugin authors: a `<file>/<table>` address reaches a table source with the inner path
  as its table, `blob_cell` joins the cell helpers, `resolve_content_container` takes
  `suffixes=None` for a kind matched by its bytes, and a text read only in part may be
  `{text, bytes}` and a reference to a missing record `{ref: {…, missing: true}}`.
