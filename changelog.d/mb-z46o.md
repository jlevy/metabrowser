- An idle server no longer spends CPU in proportion to the files under `.logs` and
  `.state`. Every 5 seconds the activity tracker reread the catalog and probed each of
  those files, which kept a server on a folder of 30,000 of them at 11–17% of a core.
  It now rereads the catalog only when the inventory changes and probes the files it
  shows as active, the files the inventory just saw change, and a bounded part of the
  rest in rotation. A write the file watcher reports shows its badge as soon as it did
  before; where no watcher reports it and a folder has more such files than one poll
  covers, the badge can take a few minutes to appear.
  The `pid_alive` label is now set only on a file shown as active.
