/* global document, localStorage, window */
// Runs before first paint so the page never flashes the wrong theme. It is a separate file, not an inline
// script, because the production CSP is script-src 'self'. Keep the key and rules in step with src/lib/theme.tsx.
(function () {
  var root = document.documentElement;
  var mode = "light";
  try {
    var stored = localStorage.getItem("pf-theme");
    if (stored === "light" || stored === "dark" || stored === "system") mode = stored;
  } catch {
    // Storage blocked: keep the default.
  }
  var dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
  root.classList.toggle("dark", dark);
})();
