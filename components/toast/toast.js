(function () {
  var VISIBLE_MS = 5000;

  function dismiss(toast) {
    if (toast.dataset.leaving) return;
    toast.dataset.leaving = "1";
    toast.classList.add("toast--leaving");
    setTimeout(function () { toast.remove(); }, 250);
  }

  document.querySelectorAll("[data-toast]").forEach(function (toast) {
    if (toast.dataset.bound) return;
    toast.dataset.bound = "1";

    var remaining = VISIBLE_MS;
    var startedAt = Date.now();
    var timer = setTimeout(function () { dismiss(toast); }, remaining);

    // Pause while the pointer or keyboard focus is on the toast, so it can be read.
    function pause() {
      clearTimeout(timer);
      remaining -= Date.now() - startedAt;
    }
    function resume() {
      startedAt = Date.now();
      timer = setTimeout(function () { dismiss(toast); }, Math.max(remaining, 1500));
    }
    toast.addEventListener("mouseenter", pause);
    toast.addEventListener("mouseleave", resume);
    toast.addEventListener("focusin", pause);
    toast.addEventListener("focusout", resume);

    toast.querySelector("[data-toast-close]").addEventListener("click", function () { dismiss(toast); });
  });
})();
