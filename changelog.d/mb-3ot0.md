- A folder created while Metabrowser is watching no longer counts twice in the file
  counts and sizes of the folders above it when two refreshes reach it at once, such as
  the watcher’s and an activity refresh, or when a file inside it changes while the
  folder is still being read.
  On a folder watched by polling, a deleted file no longer comes off the totals of the
  folders above it twice.
  A refresh now sets the totals of the folders it touches, and of those above them, from
  the files the index holds.
