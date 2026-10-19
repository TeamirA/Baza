// Product list filters: apply sort / "in stock" as soon as they change, and
// collapse the panel behind a toggle on small screens.
(function () {
  var root = document.querySelector("[data-filters]");
  if (!root) return;
  var form = root.querySelector("form");
  var toggle = root.querySelector(".filters__toggle");

  root.querySelectorAll("[data-autosubmit]").forEach(function (field) {
    field.addEventListener("change", function () { form.requestSubmit(); });
  });

  root.classList.add("filters--collapsible");
  toggle.addEventListener("click", function () {
    var open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    root.classList.toggle("filters--open", open);
  });
})();
