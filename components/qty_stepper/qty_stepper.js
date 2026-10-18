(function () {
  if (window.__qtyStepperBound) return;
  window.__qtyStepperBound = true;

  function bounds(input) {
    var min = input.min === "" ? -Infinity : Number(input.min);
    var max = input.max === "" ? Infinity : Number(input.max);
    return { min: min, max: max };
  }

  function sync(stepper) {
    var input = stepper.querySelector("input");
    var b = bounds(input);
    var value = Number(input.value) || 0;
    stepper.querySelector('[data-step="-1"]').disabled = value <= b.min;
    stepper.querySelector('[data-step="1"]').disabled = value >= b.max;
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".qty-stepper__btn");
    if (!button) return;
    var stepper = button.closest("[data-qty-stepper]");
    var input = stepper.querySelector("input");
    var b = bounds(input);
    var next = Math.min(b.max, Math.max(b.min, (Number(input.value) || 0) + Number(button.dataset.step)));
    if (String(next) === input.value) return;
    input.value = next;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    sync(stepper);
  });

  document.addEventListener("input", function (event) {
    var stepper = event.target.closest && event.target.closest("[data-qty-stepper]");
    if (stepper) sync(stepper);
  });

  document.querySelectorAll("[data-qty-stepper]").forEach(sync);
})();
