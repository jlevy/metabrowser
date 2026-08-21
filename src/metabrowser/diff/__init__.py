"""General diff rendering: the change-set model and its sources.

The format authority is ``data/file-diff-format/file-diff.schema.json``;
``format.py`` implements it, ``apply.py`` is its correctness oracle, and
``adapters/`` holds the sources. Nothing in this package mutates a
repository; acquisition (cloning, fetching, worktrees) lives outside it.
"""
