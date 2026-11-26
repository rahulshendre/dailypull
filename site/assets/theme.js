// Runs in <head>, before the page paints, so a saved theme never flashes the wrong colours.
(function () {
  try {
    var saved = JSON.parse(localStorage.getItem("dp.theme.v1"));
    if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
  } catch (e) { /* storage blocked: follow the system theme */ }
})();
