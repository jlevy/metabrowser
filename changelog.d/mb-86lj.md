- **App contract:** What the macOS app reads of `metab` is declared in one file,
  `apps/macos/metab-contract.toml`, and recorded in one golden,
  `tests/golden/app-contract.txt`: every command the app runs and every route it asks,
  with the keys and lines it reads of each answer.
  A change to either is a change to that contract, which a changelog entry now names
  with `**App contract:**`, or `**App contract fix:**` for a bug fix, and which ships in
  a minor or major release: `make lint-check` fails a branch that changes the contract
  without such an entry, and a patch release whose section holds one
  ([The App’s Contract with metab](docs/project/architecture/arch-app-contract.md)).
  `python -m devtools.check_app_contract accepts /path/to/metab` asks any `metab`
  whether it takes every command the app runs.
