- A folder created while Metabrowser is watching no longer counts twice in the file
  counts and sizes of the folders above it.
  When two refreshes reached the new folder at once, such as the watcher’s and an
  activity refresh, or a file inside it changed while the folder was still being read,
  each added the folder’s files to those totals.
  The folders above a change now take their totals from the files the index holds.
