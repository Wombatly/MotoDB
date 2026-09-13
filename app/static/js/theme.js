(function () {
  var KEY = "motodb-theme";

  function resolve(pref) {
    if (pref === "light" || pref === "dark" || pref === "logbuch") return pref;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(pref) {
    var theme = resolve(pref);
    document.documentElement.dataset.theme = theme;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      var color = theme === "dark" ? "#15171a" : theme === "logbuch" ? "#ece6d5" : "#f6efe7";
      meta.setAttribute("content", color);
    }
  }

  function read() {
    try {
      return localStorage.getItem(KEY) || "dark";
    } catch (e) {
      return "dark";
    }
  }

  window.__motodbTheme = {
    get: read,
    set: function (pref) {
      try {
        localStorage.setItem(KEY, pref);
      } catch (e) {}
      apply(pref);
    },
  };

  apply(read());

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (read() === "system") apply("system");
  });
})();
