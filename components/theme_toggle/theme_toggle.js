(function () {
  var MODES = ["system", "light", "dark"];
  var LABELS = { system: "System", light: "Light", dark: "Dark" };

  function readMode() {
    try {
      var saved = localStorage.getItem("theme");
      return saved === "light" || saved === "dark" ? saved : "system";
    } catch (e) {
      return "system";
    }
  }

  function apply(mode) {
    var root = document.documentElement;
    if (mode === "system") {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = mode;
    }
    try {
      if (mode === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", mode);
    } catch (e) {
      /* Storage blocked (private mode): the choice lasts for this page only. */
    }
  }

  function render(button, mode) {
    var next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    button.dataset.mode = mode;
    button.querySelector(".theme-toggle__label").textContent = LABELS[mode];
    button.setAttribute("aria-label", "Colour theme: " + mode + ". Switch to " + next + ".");
  }

  document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
    if (button.dataset.bound) return;
    button.dataset.bound = "1";
    render(button, readMode());
    button.addEventListener("click", function () {
      var next = MODES[(MODES.indexOf(button.dataset.mode) + 1) % MODES.length];
      apply(next);
      render(button, next);
    });
  });
})();
