- **A guided review can group its steps.** An entry of a guide’s `items` may be a group,
  a title, an optional note, and its own steps, one level deep, mixed in any order with
  steps outside a group.
  The step list names each group above its steps, which keep their numbers through the
  groups, a step’s card names its group before its place, as “Decisions · Step 2 of 12”,
  and a group’s note shows above its first step.
  A guide without groups reads as before, and the format stays `Collection/v1`
  ([Guided Review](docs/reviewing-pull-requests.md#guided-review)).

- The `guided-review` route answers each step with the guide’s `outline`, its groups and
  steps in reading order, and the step’s `group`; `MAX_ITEMS` now counts a guide’s
  groups with its steps
  ([Collection Format](docs/project/architecture/arch-collection-format.md)).

- The agent skill’s **Write a Guided Review** recommends the groups Decisions,
  Documents, Changes, Open questions, Testing, and Future work, and a concise rationale
  step for the key decisions: each one’s alternative and the fact that decided it.
