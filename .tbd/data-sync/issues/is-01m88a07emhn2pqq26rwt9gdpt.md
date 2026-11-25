---
type: is
id: is-01m88a07emhn2pqq26rwt9gdpt
title: Decide whether YAML and JSON diffs get Full and Concise views like Markdown
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T02:54:18.575Z
updated_at: 2026-11-25T02:54:18.575Z
---
Follow-up to mb-qn7e: a changed Markdown file now chooses Full | Concise | Source (diff/markdown_views.py, diff-markdown.js), while a changed YAML or JSON file keeps Rendered | Source.

A YAML or JSON tree has no runs of unchanged blocks to fold: diff-structured.js opens modified containers and whole added or removed values within ROW_BUDGET and leaves unchanged containers closed with the tree view's preview, which is already a concise view. Decide from first principles whether a Full tree (every container open) and a Concise tree (today's) are worth a third chip, what Concise would fold in a tree (unchanged siblings between changed entries?), and what a Full draw of a large tree costs against ROW_BUDGET and PAGE. If both, the chooser, refusals, route parameters (view=), goldens, and parity rows follow the Markdown pattern; if not, record why the tree keeps one rendered view.
