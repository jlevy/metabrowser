- `.csv` and `.tsv` files now open in a **Table** view, the kind’s default (`V`), with
  their text one key away in **Source** (`S`). Sort a column either way from its header,
  filter it from its header’s menu or by pressing a `true` or `false` value, search the
  text, choose columns, and open a row’s record in place of the table, by pointer or by
  the keyboard (one Tab stop, `J` and `K` or the arrows, Enter).
  `null`, an empty value, and a short row’s missing value are drawn apart; numbers are
  right-aligned; a value too long for its column is cut with its whole text in the
  tooltip. The sort, filters, search, columns, and open record are in the page’s address,
  so a link reproduces the view and Back returns to it.
  A table past a few hundred rows draws only the rows near the view; there Search stands
  in for find in page, Shift with Up or Down and Control-A or Command-A select rows that
  copy as tab-separated values, and printing prints every row read
  ([Data Tables](docs/design-system.md#data-tables)).

- **Plugin SDK:** the `table` plugin exports `mountTable(container, {path})`, the table
  view, so a plugin that serves its kind as tables gives the kind a Table view with
  `mb.plugins.load("table")` ([Table Sources](docs/plugins.md#table-sources)).
  `navigation.open(target, {replace: true})`, which replaces the history entry rather
  than pushing one, is now documented.

- The folder’s Distribution and totals tables take the new Data Tables component’s
  number and heading rules, and the unused `.data-table` and `.table-container`
  stylesheet rules are gone.
