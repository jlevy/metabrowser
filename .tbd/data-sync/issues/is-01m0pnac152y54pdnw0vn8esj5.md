---
type: is
id: is-01m0pnac152y54pdnw0vn8esj5
title: The corpus behind the headline perf claim has no command-line route
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:52.740Z
updated_at: 2026-08-23T07:11:39.738Z
---
WHAT HAPPENED. #66's headline figure -- dead time before any row exists, 19.1s -> 3.4s -- was measured on `build_project_corpus`, a corpus assembled from the repository's own locked installs. `devtools/bench_serving.py` defines that generator and `build_realistic_corpus` beside it, but `main()` wires only `build_corpus` to the CLI. Neither of the other two can be selected by any flag.

THE CONSEQUENCE. Re-running the claim requires writing a driver that imports the module and calls the generator directly, which is what validating it eventually needed. A figure that cannot be re-run by the tool that produced it is a figure that will not be re-run -- and this one was not, until a validation pass went looking.

IT ALSO EXPLAINS A NON-RESULT. Validation on a live 249,147-file tree found no dead time on EITHER build: first rows arrived in 4ms and 2ms. That neither confirms nor contradicts the claim, because the dead time is a property of the corpus shape -- deep, dependency-heavy, heavily ignored -- and a flat checkout of repositories does not have it. Reproducing it needs the corpus the claim names, which needs the flag that does not exist.

THE FIX. A `--corpus {synthetic,realistic,project}` flag selecting among the three generators, defaulting to today's behaviour so nothing changes for existing callers, and the corpus name recorded in the JSON output so a saved result says what it was measured on.

## Notes

FIXED in #73. devtools/bench_serving.py takes --corpus {synthetic,realistic,project} plus --projects for the project corpus, with the shape recorded in the JSON output and in the corpus directory name so a saved result says what it was measured on.

Confirmed by using it: the project corpus built from this flag is 247,153 files / 31,202 dirs / 251 nested .gitignore, against exp-006's stated 246,282 / 31,161 / 251. Same shape, reproducibly, from a command line.

That let exp-006's figure be tested on its own terms, which is recorded in mb-j7xx: the candidate reproduces the reported 0.81s almost exactly at 0.879s, while the baseline reads 2.53s against 13.36s reported -- most likely page-cache state, since exp-006 cleared the cache between runs and this could not.
