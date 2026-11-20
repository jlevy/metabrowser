<p align="center"><img src="icon.png" alt="Centered icon" width="192"></p>

<h1 align="center">GitHub Layout</h1>

<p align="center">A centered paragraph with a badge <img src="icon.png" alt="Badge" height="20"> in its text.</p>

## A Right-Aligned Image

<img src="icon.png" alt="Right icon" align="right" width="120">

This paragraph wraps beside an image floated to the right by its `align` attribute, as
GitHub draws one, with twenty pixels of room between the image and the text.
A README puts a project's logo or a screenshot here, beside its introduction, and the
text runs down the left side of it until it is past the image's foot.

## A Left-Aligned Image

<img src="icon.png" alt="Left icon" align="left" width="96">

This paragraph wraps beside an image floated to the left, which keeps its room on the
right, between the image and the text.

## Sized Images

<img src="icon.png" alt="By width" width="64"> <img src="icon.png" alt="By height" height="48"> <img src="icon.png" alt="By both" width="80" height="40">

## A Table With Aligned Cells

<table>
  <tr><th align="left">Left</th><th>Header</th><th align="right">Right</th></tr>
  <tr><td align="center">Centered</td><td>Default</td><td align="right">Right</td></tr>
  <tr align="right"><td>Row right</td><td align="left">Cell left</td><td>Row right</td></tr>
</table>

<div align="right">A block aligned right.</div>

## A Float That Ends the Document

<img src="icon.png" alt="Last icon" align="right" width="160">

A short last paragraph, beside an image that ends below it.

<!-- A test fixture: the layouts a README writes with the HTML attributes github.com keeps,
rendered by tests/test_markdown_github_layout_chrome.py and compared with github.com's
rendering of this file.
This document follows common-doc-guidelines.md.
-->
