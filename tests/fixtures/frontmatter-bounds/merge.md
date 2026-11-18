---
a: &a {k: v}
b: &b {<<: [*a, *a, *a, *a, *a, *a, *a, *a, *a]}
c: &c {<<: [*b, *b, *b, *b, *b, *b, *b, *b, *b]}
d: &d {<<: [*c, *c, *c, *c, *c, *c, *c, *c, *c]}
e: &e {<<: [*d, *d, *d, *d, *d, *d, *d, *d, *d]}
f: &f {<<: [*e, *e, *e, *e, *e, *e, *e, *e, *e]}
g: &g {<<: [*f, *f, *f, *f, *f, *f, *f, *f, *f]}
h: &h {<<: [*g, *g, *g, *g, *g, *g, *g, *g, *g]}
i: &i {<<: [*h, *h, *h, *h, *h, *h, *h, *h, *h]}
j: &j {<<: [*i, *i, *i, *i, *i, *i, *i, *i, *i]}
k: &k {<<: [*j, *j, *j, *j, *j, *j, *j, *j, *j]}
l: &l {<<: [*k, *k, *k, *k, *k, *k, *k, *k, *k]}
---

# Twelve Merge Levels

The body still renders.

<!-- A test fixture: front matter past its bounds, read only by tests.
This document follows common-doc-guidelines.md.
-->
