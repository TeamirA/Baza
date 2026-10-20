// Checkout: picking a saved address fills in the name and address fields.
// Choosing "A different address" clears them so a new one can be typed.
(function () {
  var picker = document.querySelector("[data-address-picker]");
  if (!picker) return;
  var form = picker.closest("form");
  var name = form.querySelector("[name=full_name]");
  var address = form.querySelector("[name=address]");
  var save = form.querySelector("[data-save-address] input");

  function update(radio, focus) {
    var isNew = radio.hasAttribute("data-new-address");
    if (isNew) {
      name.value = "";
      address.value = "";
      if (focus) name.focus();
    } else {
      name.value = radio.dataset.fullName;
      address.value = radio.dataset.address;
    }
    // A saved address is already saved; offer to save only a new one.
    if (save) {
      save.closest("label").hidden = !isNew;
      save.checked = isNew;
    }
  }

  picker.addEventListener("change", function (event) {
    if (event.target.name === "saved_address") update(event.target, true);
  });

  // Typing over a saved address turns it into a new one.
  [name, address].forEach(function (field) {
    field.addEventListener("input", function () {
      var checked = picker.querySelector("[name=saved_address]:checked");
      if (checked && !checked.hasAttribute("data-new-address") &&
          (name.value !== checked.dataset.fullName || address.value !== checked.dataset.address)) {
        picker.querySelector("[data-new-address]").checked = true;
        if (save) { save.closest("label").hidden = false; save.checked = true; }
      }
    });
  });

  var initial = picker.querySelector("[name=saved_address]:checked");
  if (initial && !initial.hasAttribute("data-new-address") && save) save.closest("label").hidden = true;
})();
