(function () {
  var RECENT_KEY = "recentSearches";
  var RECENT_MAX = 5;
  var MIN_CHARS = 2;

  function readRecent() {
    try {
      var list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(list) ? list.filter(function (q) { return typeof q === "string"; }) : [];
    } catch (e) {
      return [];
    }
  }
  function writeRecent(list) {
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX))); } catch (e) { /* storage blocked */ }
  }
  function remember(query) {
    query = query.trim();
    if (!query) return;
    var list = readRecent().filter(function (q) { return q.toLowerCase() !== query.toLowerCase(); });
    list.unshift(query);
    writeRecent(list);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;  // textContent only: never inject HTML
    return node;
  }

  document.querySelectorAll("[data-search]").forEach(function (form) {
    if (form.dataset.bound) return;
    form.dataset.bound = "1";

    var input = form.querySelector(".search__input");
    var panel = form.querySelector(".search__panel");
    var status = form.querySelector("[data-search-status]");
    var url = form.dataset.suggestUrl;
    var timer = null;
    var controller = null;
    var options = [];
    var active = -1;
    var idCounter = 0;

    function open() { panel.hidden = false; input.setAttribute("aria-expanded", "true"); }
    function close() {
      panel.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }
    function setActive(index) {
      options.forEach(function (o) { o.setAttribute("aria-selected", "false"); });
      active = index;
      if (index >= 0 && options[index]) {
        options[index].setAttribute("aria-selected", "true");
        input.setAttribute("aria-activedescendant", options[index].id);
        options[index].scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }
    function addOption(node, href) {
      node.id = "search-option-" + (++idCounter);
      node.setAttribute("role", "option");
      node.setAttribute("aria-selected", "false");
      node.dataset.href = href;
      node.addEventListener("mousedown", function (event) { event.preventDefault(); });  // keep focus in the input
      node.addEventListener("click", function () { go(node); });
      options.push(node);
      panel.appendChild(node);
    }
    function go(option) {
      if (option.dataset.query) remember(option.dataset.query);
      window.location.href = option.dataset.href;
    }
    function reset() { panel.textContent = ""; options = []; active = -1; }

    function showRecent() {
      var recent = readRecent();
      reset();
      if (!recent.length) { close(); return; }
      var heading = el("p", "search__heading", "Recent searches");
      var clear = el("button", "search__clear", "Clear");
      clear.type = "button";
      clear.addEventListener("mousedown", function (event) { event.preventDefault(); });
      clear.addEventListener("click", function () { writeRecent([]); close(); });
      heading.appendChild(clear);
      panel.appendChild(heading);
      recent.forEach(function (query) {
        var option = el("div", "search__option");
        option.appendChild(el("span", "search__name", query));
        option.dataset.query = query;
        addOption(option, form.action + "?q=" + encodeURIComponent(query));
      });
      open();
    }

    function showResults(data) {
      reset();
      if (data.corrected) {
        panel.appendChild(el("p", "search__note", "Showing matches for “" + data.corrected + "”"));
      }
      data.results.forEach(function (item) {
        var option = el("div", "search__option");
        if (item.image) {
          var img = el("img", "search__thumb");
          img.src = item.image;
          img.alt = "";
          img.loading = "lazy";
          option.appendChild(img);
        } else {
          option.appendChild(el("span", "search__thumb search__thumb--letter", item.name.charAt(0)));
        }
        var text = el("span", "search__text");
        text.appendChild(el("span", "search__name", item.name));
        text.appendChild(el("span", "search__meta", (item.category ? item.category + " · " : "") + (item.in_stock ? "In stock" : "Sold out")));
        option.appendChild(text);
        option.appendChild(el("span", "search__price", "$" + item.price));
        option.dataset.query = data.query;
        addOption(option, item.url);
      });
      if (data.results.length) {
        var all = el("div", "search__option search__all",
          data.total > data.results.length ? "See all " + data.total + " results" : "See results for “" + data.query + "”");
        all.dataset.query = data.query;
        addOption(all, data.see_all_url);
      } else {
        panel.appendChild(el("p", "search__note", "No products match “" + data.query + "”."));
      }
      status.textContent = data.results.length
        ? data.total + " result" + (data.total === 1 ? "" : "s") + " available. Use the arrow keys to browse."
        : "No results.";
      open();
    }

    function fetchSuggestions(query) {
      if (controller) controller.abort();
      controller = new AbortController();
      fetch(url + "?q=" + encodeURIComponent(query), { signal: controller.signal, headers: { Accept: "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && input.value.trim() === data.query && document.activeElement === input) showResults(data);
        })
        .catch(function () { /* aborted or offline: keep the plain form working */ });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      var query = input.value.trim();
      if (query.length < MIN_CHARS) {
        if (controller) controller.abort();
        if (!query) showRecent(); else close();
        return;
      }
      timer = setTimeout(function () { fetchSuggestions(query); }, 150);
    });
    input.addEventListener("focus", function () {
      if (!input.value.trim()) showRecent();
    });
    input.addEventListener("blur", function () { setTimeout(close, 120); });
    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (panel.hidden) { input.value.trim() ? fetchSuggestions(input.value.trim()) : showRecent(); return; }
        event.preventDefault();
        var step = event.key === "ArrowDown" ? 1 : -1;
        setActive(options.length ? (active + step + options.length) % options.length : -1);
      } else if (event.key === "Enter" && active >= 0 && !panel.hidden) {
        event.preventDefault();
        go(options[active]);
      } else if (event.key === "Escape" && !panel.hidden) {
        event.preventDefault();
        close();
      }
    });
    form.addEventListener("submit", function () { remember(input.value); });
  });
})();
