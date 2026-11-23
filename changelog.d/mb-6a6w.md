- **A pull request’s page follows new pushes.** Code served on a pull request’s head now
  moves to the new head when commits are pushed, as a page on a branch does, so **Switch
  to the head** is gone.
  A commit opened by its ID still stays put, and when it was the head, the foot of the
  navigation pane offers the newer one with **Switch**. The same holds for a branch’s
  tip: View file’s way back to it by ID no longer follows the branch, and when the
  branch moves on, its **Switch** offer is back.
  **Changes** shows the new head’s diff by itself, with a line naming the head it showed
  and the head it shows, and **Show the earlier changes** to go back.
  It keeps your file, and your place in it, where the new diff still has the file.
  See [Staying Current](docs/reviewing-pull-requests.md#staying-current).
