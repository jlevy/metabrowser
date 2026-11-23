- In a repository folder, a branch or tag chosen in the Files chooser now follows it:
  when you commit on the branch shown, or your own `git fetch` moves `origin/main`, the
  page goes to the new commit by itself within a few seconds, on the same file or folder
  when the new commit has it, or at the root.
  Metabrowser reads the checkout’s refs to see the move and fetches and writes nothing;
  a commit opened by its ID stays that commit, and **Working tree** is always the files
  on disk
  ([browsing history](docs/browsing-history.md#branches-and-tags-of-a-local-checkout)).
  `GET /api/source/status` reports such a revision with `follows` true, `latest`, and
  `probe_every_s`, and `POST /api/source/refresh` with `{"for": "page"}` answers
  `probed` on a folder that shows one, where a folder with no store of its origin
  answered `409`.
