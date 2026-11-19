- The branch and tag chooser is in the Files tab’s toolbar, before Group by, instead of
  above the tabs, since it chooses what the Files tab shows and nothing else.
  The Commits tab no longer follows it.
  A local checkout’s Commits tab shows the checkout’s history whichever branch or tag
  the Files tab shows, and keeps working when another tab switches the server; a
  commit’s page is read as before.
  A repository URL’s Commits tab shows the default branch’s history whichever branch,
  tag, or commit the Files tab shows, so a `/tree/<branch>` or `/pull/<n>` address no
  longer narrows it to that branch’s or pull request’s commits.
  When another tab switches a checkout’s server, the offer to reload is at the foot of
  the pane, where every tab shows it, as a mirror’s freshness row is.
  Each branch and tag in the chooser’s list shows its commit’s short ID in the commit-ID
  face and that commit’s age, with the exact time as its tooltip, a tag’s being its
  commit’s. A commit’s short ID has one length in the list, on the button, in the
  navigation heading, and in a mirror’s offer of a newer commit, which now shows it in
  the commit-ID face. The working tree row names the folder by its path, with the
  folder’s own name kept whole, in place of “Live local files”.
  `GET /api/source/refs` rows gain `committed_at`, and its `working_tree` gains the
  folder’s `name` and `location`.
