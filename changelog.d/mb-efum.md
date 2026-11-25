- **A Pulls row and a stack’s heading leave out a line total of zero.** A pull request
  that only adds lines reads “+1,234” rather than “+1,234 −0”, one that only deletes
  them reads “−567”, and one that changes no lines reads a gray “0 lines”; one that adds
  and deletes still shows both.
  The Diff summary, a commit’s hover card, and a pull request’s page keep both totals.
  Plugins can ask for the same line with
  `metabrowser.changeLine(change, {omitZeroTotals: true})`
  ([Brief Change Line](docs/design-system.md#brief-change-line)).
