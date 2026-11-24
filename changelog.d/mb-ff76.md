- `/api/rollup` selects the largest children of each folder it expands instead of
  sorting all of them, so a rollup that reaches a folder holding many thousands of files
  answers faster, with the same response.
