// Sample plugin with sidekick — exercises the data-hook contract.
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    return;
  }

  mb.registerView("sidekick-doc", "summary", {
    async render(container, ctx) {
      const data = await mb.fetchPluginData("sidekick-sample", "echo", {
        msg: "hi",
        path: ctx.path,
      });
      container.innerHTML =
        "<div class='mb-plugin-sidekick-sample'>" +
        "<p>Echo: " +
        mb.escapeHtml(data.echo || "") +
        "</p>" +
        "<p>Path: " +
        mb.escapeHtml(data.path || "") +
        "</p>" +
        "</div>";
    },
  });
})();
