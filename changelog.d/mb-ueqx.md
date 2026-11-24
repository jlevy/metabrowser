- A Markdown file in a diff with bytes that are not UTF-8, a NUL, or lines that end at a
  carriage return alone renders in Rendered as the Document view renders it, where it
  showed only Source before.

- A JSON file in a diff with a key twice in one object renders in Rendered as the file
  view’s tree draws it, the key once with its last value, where it showed only Source
  before; a change to a value the repeated key hides, or an added or deleted file that
  hides one, is a change **Source** shows.
  YAML with a key twice in one mapping still opens in Source, as the file view shows it
  without a tree.
