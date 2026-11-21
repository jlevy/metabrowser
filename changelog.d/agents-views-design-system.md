- A link no rule colors is now the design’s link color everywhere, not the browser’s
  default blue and visited purple: the shell sets a zero-specificity base anchor color
  ([Links Have a Base Color](docs/design-system.md#links-have-a-base-color)), which
  plugin authors’ bare links inherit and any context’s own rule still overrides.

- The agents views follow the design system.
  Session links are `--link` with an underline on hover and the focus ring, the home’s
  agent line uses the design’s separator in place of a stray “.”, Running now and Recent
  sessions are two-line rows whose age stays at the end of the first line however long
  the project path is, section titles and the page title use the shell’s headings, and
  the session list’s table scrolls in a keyboard-reachable wrap
  ([The Agents Views](docs/design-system.md#the-agents-views)).
