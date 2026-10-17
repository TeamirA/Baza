// Show a spinner on the submit button of POST forms and block double submits
// (e.g. paying twice or adding an item twice). Opt out with data-no-loading.
(function () {
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== "post" || form.hasAttribute("data-no-loading")) {
      return;
    }
    if (form.dataset.submitting) {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "1";
    form.setAttribute("aria-busy", "true");

    var button = event.submitter || form.querySelector("[type=submit]");
    if (button) {
      button.classList.add("is-loading");
      // Disable after the browser has captured the button's name/value for this submit.
      setTimeout(function () { button.disabled = true; }, 0);
    }
  });

  // Coming back via the back button restores the page from cache: re-enable it.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    document.querySelectorAll("form[data-submitting]").forEach(function (form) {
      delete form.dataset.submitting;
      form.removeAttribute("aria-busy");
      form.querySelectorAll(".is-loading").forEach(function (button) {
        button.classList.remove("is-loading");
        button.disabled = false;
      });
    });
  });
})();
