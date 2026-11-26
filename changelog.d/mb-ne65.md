- **A diff no longer moves under the reader when a rendered document arrives late.** On
  a pull request’s Changes and Docs, and in any diff with Markdown, YAML, or JSON files,
  a file near the first screen whose rendered view was slow showed its Source first and
  then swapped it for the rendering, which moved every file below it, sometimes under a
  press already aimed.
  Such a file now shows its bar and its progress mark until its rendered view comes, and
  the files after it show only then, in the places they keep.
