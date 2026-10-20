(function () {
  if (window.__wishlistBound) return;
  window.__wishlistBound = true;

  // Toggle without leaving the page; the form still works without JavaScript.
  document.addEventListener("submit", function (event) {
    var form = event.target.closest && event.target.closest("[data-wishlist]");
    if (!form) return;
    event.preventDefault();
    var button = form.querySelector(".wishlist__button");
    if (button.disabled) return;
    button.disabled = true;
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
      .then(function (data) {
        // Update every heart for this product on the page, and the header count.
        document.querySelectorAll('[data-wishlist][action="' + form.getAttribute("action") + '"] .wishlist__button').forEach(function (b) {
          b.setAttribute("aria-pressed", String(data.saved));
          b.setAttribute("aria-label", (data.saved ? "Remove " : "Save ") + b.dataset.name + (data.saved ? " from saved" : ""));
          var label = b.querySelector(".wishlist__label");
          if (label) label.textContent = data.saved ? "Saved" : "Save";
        });
        document.querySelectorAll("[data-wishlist-count]").forEach(function (badge) {
          badge.textContent = data.count;
          badge.hidden = !data.count;
        });
      })
      .catch(function () { form.submit(); })  // fall back to a normal post
      .finally(function () { button.disabled = false; });
  });
})();
