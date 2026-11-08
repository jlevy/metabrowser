const { pullSearchSession } = require("./search-palette-behavior.js");

pullSearchSession().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
