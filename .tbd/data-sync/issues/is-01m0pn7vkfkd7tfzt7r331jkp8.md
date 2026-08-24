---
type: is
id: is-01m0pn7vkfkd7tfzt7r331jkp8
title: "Stability for 0.6.1: validating the perf work, and the measurement errors that cost time doing it"
kind: epic
status: open
priority: 1
version: 15
labels: []
dependencies: []
child_order_hints:
  - is-01m0pna98v9jhzg2h3jpvzpj1m
  - is-01m0pna9mf444e07mx8mvh9ch9
  - is-01m0pna9z3ztf64bs18vp0zw6s
  - is-01m0pnaa9w92wx4zyt81c876ds
  - is-01m0pnaame8v4dybf2mw00nmkf
  - is-01m0pnaaz10y8mk2vz51xsha0z
  - is-01m0pnab9fwe6q3j8vbdvp6hfg
  - is-01m0pnabncfm4ztxc24s6mnxk8
  - is-01m0pnac152y54pdnw0vn8esj5
  - is-01m0p8c31yfhs5sxy0qt6nztvw
  - is-01m0pmgjhkfhhg2whf99q8693d
  - is-01m0pqdwbs6t1tfbmhyn4b065q
  - is-01m0s89fnaknv3z2nxh16mh8tg
  - is-01m0s8aj66bkeprhxw8ar6hed5
created_at: 2026-08-23T06:34:30.382Z
updated_at: 2026-08-24T06:46:30.853Z
---
The perf work in #66 and #68 landed on main after 0.6.0 shipped. This epic covers proving it is genuine, proving it changed no behaviour, and recording the measurement errors made while doing so -- because every one of them produced a confident wrong answer, and every one is cheap to repeat.

TWO QUESTIONS THIS EPIC ANSWERS.

Is it faster? Partly established: on a live 249,147-file tree the full index went 32.5s -> 19.1s (~1.7x), medians of two interleaved runs, and the candidate's spread was 30x tighter. Not established: #66's headline figure, 19.1s -> 3.4s of dead time before any row exists, which needs the corpus it was measured on.

Does it behave the same? Established at the channel the browser uses: `/api/tree?depth=0` shows zero differences, and on a quarter-million-file tree both builds report identical row counts, file counts and byte totals. One deliberate difference exists at depth>=1 and is filed as mb-amyt.

WHY THE ERRORS ARE TRACKED AS WORK. Each of the children below is a real mistake made during this validation, and not one of them announced itself -- a broken harness looked like a slow build, a mutating corpus looked like a behaviour change, and an endpoint nobody uses looked like a regression. The fix in every case is a check or a docstring that makes the next run fail loudly instead of quietly. They are filed individually so each can be fixed and closed rather than surviving as a paragraph in a report.
