- A repository opened by its URL now shows a branch as the mirror last fetched it, the
  way github.com does.
  When a fetch moves the branch or tag you are reading, the page follows it to the new
  commit by itself, on the same file when the new commit has it, in place of the old
  “main is now at … **Switch**” offer at the foot of the navigation pane.
  A commit opened by its ID stays put, and a pull request’s new head is still offered
  with **Switch**. `GET /api/source/status` gains `follows`, which says whether the
  served pin moves with its ref.
  See
  [Following a Branch](docs/project/architecture/arch-mirror-acquisition-and-refresh.md#following-a-branch).
