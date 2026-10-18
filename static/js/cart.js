// Submit a cart line's quantity form automatically when the number changes,
// so the "Update" button is only needed when JavaScript is off. The delay lets
// several quick taps on the stepper's + / − buttons go out as one update.
document.querySelectorAll(".js-autosubmit").forEach((form) => {
  const input = form.querySelector("input[name=quantity]");
  const fallback = form.querySelector(".js-autosubmit-fallback");
  if (fallback) fallback.hidden = true;
  let timer;
  input.addEventListener("change", () => {
    clearTimeout(timer);
    timer = setTimeout(() => form.requestSubmit(), 600);
  });
});
