- In a repository folder, the row under the Files tab now says which view you are on.
  On the working tree it reads “Working tree · main”, naming the branch the files on
  disk are on, or the commit when `HEAD` is detached.
  Opening the list picks up a branch you switched to in a terminal since the page
  loaded. A branch, tag, or remote branch chosen from the list reads “Revision · feature”
  and ends with a **Working tree** button that takes you back in one click.
  Before, the row named only the branch, so the working tree and the checked-out
  branch’s last commit looked the same, and choosing **Working tree** seemed to do
  nothing. The list also marks the one you are on with the highlight a Pulls row uses
  ([browsing history](docs/browsing-history.md#branches-and-tags-of-a-local-checkout)).
