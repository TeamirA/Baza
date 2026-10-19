(function () {
  document.querySelectorAll("[data-gallery]").forEach(function (gallery) {
    if (gallery.dataset.bound) return;
    gallery.dataset.bound = "1";

    var track = gallery.querySelector(".gallery__track");
    var slides = Array.prototype.slice.call(gallery.querySelectorAll(".gallery__slide"));
    var thumbs = Array.prototype.slice.call(gallery.querySelectorAll(".gallery__thumb"));
    var dialog = gallery.querySelector(".gallery__zoom");
    var zoomImg = gallery.querySelector(".gallery__zoom-img");

    function current() {
      return Math.round(track.scrollLeft / Math.max(track.clientWidth, 1));
    }
    function show(index) {
      index = Math.max(0, Math.min(slides.length - 1, index));
      track.scrollTo({ left: index * track.clientWidth });
    }
    function markThumb() {
      var index = current();
      thumbs.forEach(function (thumb, i) {
        if (i === index) thumb.setAttribute("aria-current", "true");
        else thumb.removeAttribute("aria-current");
      });
    }

    thumbs.forEach(function (thumb) {
      thumb.addEventListener("click", function () { show(Number(thumb.dataset.index)); });
    });
    var scrollTimer;
    track.addEventListener("scroll", function () {
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(markThumb, 60);
    });
    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") { show(current() + 1); event.preventDefault(); }
      if (event.key === "ArrowLeft") { show(current() - 1); event.preventDefault(); }
    });

    if (!dialog || typeof dialog.showModal !== "function") return;
    slides.forEach(function (slide) {
      slide.addEventListener("click", function () {
        var img = slide.querySelector("img");
        zoomImg.src = slide.dataset.zoom;
        zoomImg.alt = img ? img.alt : "";
        dialog.showModal();
      });
    });
    // Click the photo, the backdrop or the close button to leave; Esc works natively.
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog || event.target === zoomImg || event.target.closest("[data-zoom-close]")) {
        dialog.close();
      }
    });
  });
})();
