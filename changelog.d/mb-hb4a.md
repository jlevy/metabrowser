- The Pulls tab reads the lines changed of every row it draws in one request again.
  When the browser was idle between drawing the first rows and drawing them again at
  their measured heights, the rows that second drawing added waited in their placeholder
  for a second request until the first had answered.
