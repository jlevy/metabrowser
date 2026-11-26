- **A stack’s row in the Pulls tab says how big and how fresh the stack is.** It reads
  “Stack #286 · 4 pulls”, the number bold, with the age of the stack’s most recent
  change at the row’s end, whether the stack is open or closed.
  The age is the newest update among the stack’s pull requests in the list.
  The lines the stack changes moved to its Whole stack row
  ([Stack Groups in the Pulls Tab](docs/design-system.md#stack-groups-in-the-pulls-tab)).

- **Whole stack holds the stack’s pull requests.** The row under an open stack reads
  “Whole stack · +1,234 −567” and has a chevron that hides and shows the stack’s pull
  requests, which sit a level further in and are shown by default.
  A press on the chevron toggles them; a press anywhere else on the row still opens the
  stack’s page. Right and Left walk the levels as in a tree: Right on Whole stack shows
  the pull requests or goes to the first, Left hides them or goes to the stack’s row,
  Left on a pull request goes to Whole stack, and Space on Whole stack now shows or
  hides the pull requests instead of opening the stack’s page, which Enter opens.
  Opening a pull request that is hidden reveals it.
